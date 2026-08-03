"""USFWS image metadata ingestion for caller-supplied bird species.

The source deliberately preserves search and media-page metadata without
applying a license policy. Commercial-use eligibility is a publication concern
implemented by ``rufous_public.usfws_commercial_image``.

API: https://www.fws.gov/fws_search/search_images
Media pages: https://www.fws.gov/media/{slug}
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import dlt
import pendulum
from dlt.sources.helpers import requests as dlt_requests

from databox_sources._logging import get_logger

log = get_logger("databox_sources.usfws")

USFWS_BASE_URL = "https://www.fws.gov"
USFWS_IMAGE_SEARCH_URL = f"{USFWS_BASE_URL}/fws_search/search_images"
USFWS_GLOBAL_SEARCH_URL = f"{USFWS_BASE_URL}/fws_search/global_search"
USFWS_PAGE_SIZE = 100
USFWS_MAX_IMAGES_PER_TARGET = 500
USFWS_MAX_TARGET_SPECIES = 500
USFWS_MAX_TOTAL_CANDIDATES = 10_000
USFWS_MAX_DETAIL_PAGES = 10_000
USFWS_MAX_UNAVAILABLE_DETAILS = 10
USFWS_REQUEST_TIMEOUT_SECONDS = 30
USFWS_REQUEST_MAX_ATTEMPTS = 6
USFWS_RETRY_BASE_SECONDS = 1.0
USFWS_RETRY_MAX_SECONDS = 30.0
USFWS_MAX_SEARCH_RESPONSE_BYTES = 8 * 1024 * 1024
USFWS_MAX_DETAIL_RESPONSE_BYTES = 4 * 1024 * 1024
USFWS_RESPONSE_CHUNK_BYTES = 64 * 1024
USFWS_DETAIL_WORKERS = 3
USFWS_MAX_DETAIL_WORKERS = 4
USFWS_USER_AGENT = "loughondata.com Rufous bird-media showcase (connor@loughondata.com)"

_TEXT_LIMIT = 300
_SPECIES_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_SAFE_MEDIA_PATH_PATTERN = re.compile(r"^/media/[a-z0-9][a-z0-9-]*$")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_DATE_PATTERN = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_DIMENSION_PATTERN = re.compile(r"\((\d+)\s*x\s*(\d+)\)", re.IGNORECASE)

_RUN_COLUMNS: Any = {
    "run_id": {"data_type": "text"},
    "status": {"data_type": "text"},
    "target_species_count": {"data_type": "bigint"},
    "completed_target_species_count": {"data_type": "bigint"},
    "record_count": {"data_type": "bigint"},
    "started_at": {"data_type": "timestamp"},
    "completed_at": {"data_type": "timestamp"},
    "search_endpoint": {"data_type": "text"},
    "page_size": {"data_type": "bigint"},
    "max_images_per_target": {"data_type": "bigint"},
    "request_max_attempts": {"data_type": "bigint"},
    "detail_worker_count": {"data_type": "bigint"},
    "_loaded_at": {"data_type": "timestamp"},
}

_IMAGE_COLUMNS: Any = {
    "run_id": {"data_type": "text"},
    "species_code": {"data_type": "text"},
    "target_common_name": {"data_type": "text"},
    "target_scientific_name": {"data_type": "text"},
    "media_id": {"data_type": "text"},
    "discovery_method": {"data_type": "text"},
    "source_page_url": {"data_type": "text"},
    "search_result_page_href": {"data_type": "text"},
    "search_result_title": {"data_type": "text"},
    "search_result_caption": {"data_type": "text"},
    "search_result_credit": {"data_type": "text"},
    "search_result_image_url": {"data_type": "text"},
    "search_result_alt_text": {"data_type": "text"},
    "search_result_width": {"data_type": "bigint"},
    "search_result_height": {"data_type": "bigint"},
    "search_result_published_at": {"data_type": "text"},
    "search_result_mime_label": {"data_type": "text"},
    "detail_fetch_status": {"data_type": "text"},
    "source_title": {"data_type": "text"},
    "source_caption": {"data_type": "text"},
    "source_alt_text": {"data_type": "text"},
    "source_creator": {"data_type": "text"},
    "source_license": {"data_type": "text"},
    "source_license_url": {"data_type": "text"},
    "source_published_at": {"data_type": "text"},
    "source_created_text": {"data_type": "text"},
    "source_media_type": {"data_type": "text"},
    "source_mime_type": {"data_type": "text"},
    "source_image_medium_url": {"data_type": "text"},
    "source_image_medium_width": {"data_type": "bigint"},
    "source_image_medium_height": {"data_type": "bigint"},
    "source_image_original_url": {"data_type": "text"},
    "source_image_original_width": {"data_type": "bigint"},
    "source_image_original_height": {"data_type": "bigint"},
    "scientific_name_tags_json": {"data_type": "text"},
    "species_tag_urls_json": {"data_type": "text"},
    "subject_tags_json": {"data_type": "text"},
    "_search_endpoint": {"data_type": "text"},
    "_loaded_at": {"data_type": "timestamp"},
}


@dataclass(frozen=True)
class TargetSpecies:
    """One explicit species identity supplied by the snapshot caller."""

    species_code: str
    common_name: str
    scientific_name: str


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list[_Node] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def text(self) -> str:
        values = [*self.text_parts, *(child.text() for child in self.children)]
        return _clean_text(" ".join(value for value in values if value)) or ""

    def descendants(self) -> Iterator[_Node]:
        for child in self.children:
            yield child
            yield from child.descendants()

    def first_class(self, class_name: str) -> _Node | None:
        return next((node for node in self.descendants() if class_name in node.classes), None)

    def first_tag(self, tag: str) -> _Node | None:
        return next((node for node in self.descendants() if node.tag == tag), None)


class _TreeParser(HTMLParser):
    _VOID_ELEMENTS = frozenset(
        {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {name: value or "" for name, value in attrs})
        self._stack[-1].children.append(node)
        if tag not in self._VOID_ELEMENTS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].text_parts.append(data)


@dataclass
class _SearchCandidate:
    page_href: str
    source_page_url: str
    media_id: str
    title: str | None
    caption: str | None
    credit: str | None
    image_url: str | None
    alt_text: str | None
    width: int | None
    height: int | None
    published_at: str | None
    mime_label: str | None
    discovery_methods: set[str] = field(default_factory=set)
    discovery_endpoints: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _Snapshot:
    run: dict[str, Any]
    records: tuple[dict[str, Any], ...]


class _RequestRetriesExhaustedError(RuntimeError):
    """A transient USFWS request remained unavailable after bounded retries."""


class _ResponseBodyValidationError(RuntimeError):
    """A USFWS response body could not be accepted safely."""


class _ResponseBodyTooLargeError(_ResponseBodyValidationError):
    """A USFWS response exceeded its reviewed in-memory body bound."""


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _WHITESPACE_PATTERN.sub(" ", value).strip()
    return cleaned or None


def _bounded_text(value: Any, *, field_name: str) -> str:
    text = _clean_text(str(value) if value is not None else None)
    if text is None:
        raise ValueError(f"USFWS target {field_name} is required")
    if len(text) > _TEXT_LIMIT or any(ord(char) < 32 for char in text):
        raise ValueError(f"USFWS target {field_name} is invalid")
    return text


def _normalize_targets(
    target_species: Sequence[Mapping[str, str]] | None,
) -> tuple[TargetSpecies, ...]:
    if not target_species:
        return ()
    if len(target_species) > USFWS_MAX_TARGET_SPECIES:
        raise ValueError(f"USFWS supports at most {USFWS_MAX_TARGET_SPECIES} target species")
    targets: list[TargetSpecies] = []
    seen_codes: set[str] = set()
    for raw in target_species:
        species_code = _bounded_text(raw.get("species_code"), field_name="species_code")
        common_name = _bounded_text(raw.get("common_name"), field_name="common_name")
        scientific_name = _bounded_text(raw.get("scientific_name"), field_name="scientific_name")
        if not _SPECIES_CODE_PATTERN.fullmatch(species_code):
            raise ValueError("USFWS target species_code contains unsupported characters")
        if species_code in seen_codes:
            raise ValueError(f"USFWS target species_code is duplicated: {species_code}")
        seen_codes.add(species_code)
        targets.append(TargetSpecies(species_code, common_name, scientific_name))
    return tuple(targets)


def _parse_html(html: str) -> _Node:
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return parser.root


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _absolute_url(value: str | None) -> str | None:
    return urljoin(f"{USFWS_BASE_URL}/", value) if value else None


def _safe_media_page_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.fws.gov"
        and parsed.port is None
        and not parsed.query
        and not parsed.fragment
        and bool(_SAFE_MEDIA_PATH_PATTERN.fullmatch(parsed.path))
    )


def _field_text(root: _Node, class_name: str) -> str | None:
    node = root.first_class(class_name)
    return node.text() if node is not None else None


def _credit_text(root: _Node) -> str | None:
    node = root.first_class("image-credit")
    if node is None:
        return None
    paragraph = node.first_tag("p")
    if paragraph is not None:
        return paragraph.text() or None
    value = node.text()
    if value and value.startswith("Photo By/Credit"):
        value = value.removeprefix("Photo By/Credit").strip()
    return value or None


def parse_search_card(html: str) -> _SearchCandidate:
    """Parse one rendered search-result fragment without filtering its metadata."""
    root = _parse_html(html)
    title_field = root.first_class("field--name-name")
    title_link = title_field.first_tag("a") if title_field else None
    media_field = root.first_class("field--name-field-media-image")
    media_link = media_field.first_tag("a") if media_field else None
    link = title_link or media_link
    page_href = link.attrs.get("href", "") if link else ""
    source_page_url = _absolute_url(page_href) or ""
    image = media_field.first_tag("img") if media_field else None
    time_node = root.first_tag("time")
    path = urlparse(source_page_url).path
    slug = path.removeprefix("/media/") if path.startswith("/media/") else ""
    media_id = (
        slug
        or hashlib.sha256(
            f"{page_href}|{_field_text(root, 'field--name-name')}".encode()
        ).hexdigest()
    )
    return _SearchCandidate(
        page_href=page_href,
        source_page_url=source_page_url,
        media_id=media_id,
        title=_field_text(root, "field--name-name"),
        caption=_field_text(root, "field--name-field-media-caption"),
        credit=_field_text(root, "field--name-field-media-credit"),
        image_url=_absolute_url(image.attrs.get("src")) if image else None,
        alt_text=_clean_text(image.attrs.get("alt")) if image else None,
        width=_as_int(image.attrs.get("width")) if image else None,
        height=_as_int(image.attrs.get("height")) if image else None,
        published_at=time_node.attrs.get("datetime") if time_node else None,
        mime_label=_field_text(root, "field--name-field-mime-type"),
    )


def _item_values(field_node: _Node | None) -> tuple[list[str], list[str]]:
    if field_node is None:
        return [], []
    items = [node for node in field_node.descendants() if "field--item" in node.classes]
    values: list[str] = []
    urls: list[str] = []
    for item in items:
        text = item.text()
        if text:
            values.append(text)
        link = item.first_tag("a")
        if link and link.attrs.get("href"):
            urls.append(_absolute_url(link.attrs["href"]) or link.attrs["href"])
    return values, urls


def _rights_values(field_node: _Node | None) -> tuple[str | None, str | None, str]:
    """Return one unambiguous rights assertion or JSON-encoded raw evidence.

    Rights are intentionally stricter than ordinary tag fields. A media page
    must expose exactly one non-empty usage-rights item, with at most one link,
    before the assertion is marked ``ok``. Multiple items or links are kept as
    JSON arrays in the existing raw text columns so no contradictory evidence
    is silently discarded by selecting the first value.
    """
    if field_node is None:
        return None, None, "missing_rights"
    items = [node for node in field_node.descendants() if "field--item" in node.classes]
    values: list[str] = []
    urls: list[str] = []
    for item in items:
        text = item.text()
        if text:
            values.append(text)
        for node in item.descendants():
            if node.tag == "a" and node.attrs.get("href"):
                urls.append(_absolute_url(node.attrs["href"]) or node.attrs["href"])

    if len(items) == 1 and len(values) == 1 and len(urls) <= 1:
        return values[0], urls[0] if urls else None, "ok"
    if not values and not urls:
        return None, None, "missing_rights"
    return (
        json.dumps(values, ensure_ascii=True, separators=(",", ":")),
        json.dumps(urls, ensure_ascii=True, separators=(",", ":")),
        "ambiguous_rights",
    )


def _download_link(root: _Node, suffix: str) -> _Node | None:
    return next(
        (
            node
            for node in root.descendants()
            if node.tag == "a" and node.attrs.get("download", "").endswith(suffix)
        ),
        None,
    )


def _picture_fallback(root: _Node) -> tuple[str | None, int | None, int | None]:
    sources = [
        node
        for node in root.descendants()
        if node.tag == "source"
        and node.attrs.get("srcset")
        and node.attrs.get("type", "").lower() != "image/webp"
    ]
    choices = sorted(
        (
            (_as_int(node.attrs.get("width")) or 0, node)
            for node in sources
            if (_as_int(node.attrs.get("width")) or 0) <= 992
        ),
        reverse=True,
        key=lambda item: item[0],
    )
    node = choices[0][1] if choices else None
    if node is None:
        image = root.first_tag("img")
        if image is None:
            return None, None, None
        return (
            _absolute_url(image.attrs.get("src")),
            _as_int(image.attrs.get("width")),
            _as_int(image.attrs.get("height")),
        )
    srcset = node.attrs["srcset"].split()[0]
    return (
        _absolute_url(srcset),
        _as_int(node.attrs.get("width")),
        _as_int(node.attrs.get("height")),
    )


def _iso_created_date(value: str | None) -> str | None:
    if not value:
        return None
    match = _DATE_PATTERN.search(value)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def parse_media_page(html: str) -> dict[str, Any]:
    """Parse the auditable rights and image fields from one FWS media page."""
    root = _parse_html(html)
    content = root.first_class("media-full-content") or root
    photoswipe = content.first_class("photoswipe")
    original_url = _absolute_url(photoswipe.attrs.get("href")) if photoswipe else None
    original_width = _as_int(photoswipe.attrs.get("data-pswp-width")) if photoswipe else None
    original_height = _as_int(photoswipe.attrs.get("data-pswp-height")) if photoswipe else None
    overlay_title = _clean_text(photoswipe.attrs.get("data-overlay-title")) if photoswipe else None

    medium = _download_link(content, "-medium")
    if medium:
        medium_url = _absolute_url(medium.attrs.get("href"))
        dimensions = _DIMENSION_PATTERN.search(medium.text())
        medium_width = int(dimensions.group(1)) if dimensions else None
        medium_height = int(dimensions.group(2)) if dimensions else None
    else:
        medium_url, medium_width, medium_height = _picture_fallback(content)

    image_field = content.first_class("field--name-field-media-image")
    image = image_field.first_tag("img") if image_field else content.first_tag("img")
    license_field = content.first_class("field--name-field-creative-commons-license")
    source_license, source_license_url, rights_status = _rights_values(license_field)
    species_items, species_urls = _item_values(content.first_class("field--name-field-species-ref"))
    subject_items, _ = _item_values(content.first_class("field--name-field-subject-tags"))
    created_text = _field_text(content, "date-shot-created")
    title = overlay_title or _field_text(content, "field--name-name")
    if not title:
        heading = content.first_tag("h1") or root.first_tag("h1")
        title = heading.text() if heading else None
    # The public interface publishes the medium image, so its declared MIME
    # must describe that exact URL rather than a potentially different-format
    # original download.
    mime_type = mimetypes.guess_type(urlparse(medium_url or "").path)[0]
    return {
        "detail_fetch_status": rights_status,
        "source_title": title,
        "source_caption": _field_text(content, "field--name-field-media-caption"),
        "source_alt_text": _clean_text(image.attrs.get("alt")) if image else None,
        "source_creator": _credit_text(content),
        "source_license": source_license,
        "source_license_url": source_license_url,
        "source_published_at": _iso_created_date(created_text),
        "source_created_text": created_text,
        "source_media_type": _field_text(content, "media-type"),
        "source_mime_type": mime_type,
        "source_image_medium_url": medium_url,
        "source_image_medium_width": medium_width,
        "source_image_medium_height": medium_height,
        "source_image_original_url": original_url,
        "source_image_original_width": original_width,
        "source_image_original_height": original_height,
        "scientific_name_tags_json": json.dumps(species_items, separators=(",", ":")),
        "species_tag_urls_json": json.dumps(species_urls, separators=(",", ":")),
        "subject_tags_json": json.dumps(subject_items, separators=(",", ":")),
    }


def _http_get(url: str, **kwargs: Any) -> Any:
    return dlt_requests.get(url, **kwargs)


def _bounded_response_body(response: Any, *, maximum_bytes: int, label: str) -> bytes:
    """Read a streamed response without ever accepting an unbounded body."""
    headers = getattr(response, "headers", None)
    content_length = headers.get("Content-Length") if isinstance(headers, Mapping) else None
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError):
            raise _ResponseBodyValidationError(
                f"USFWS {label} response has an invalid Content-Length"
            ) from None
        if declared_length < 0:
            raise _ResponseBodyValidationError(
                f"USFWS {label} response has an invalid Content-Length"
            )
        if declared_length > maximum_bytes:
            raise _ResponseBodyTooLargeError(
                f"USFWS {label} response exceeds the {maximum_bytes}-byte limit"
            )

    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        chunks = iterator(chunk_size=USFWS_RESPONSE_CHUNK_BYTES)
    else:
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            raise _ResponseBodyValidationError(
                f"USFWS {label} response does not expose a byte body"
            )
        chunks = (content,)

    body = bytearray()
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise _ResponseBodyValidationError(f"USFWS {label} response contains a non-byte chunk")
        if len(chunk) > maximum_bytes - len(body):
            raise _ResponseBodyTooLargeError(
                f"USFWS {label} response exceeds the {maximum_bytes}-byte limit"
            )
        body.extend(chunk)
    if not body:
        raise _ResponseBodyValidationError(f"USFWS {label} response body is empty")
    return bytes(body)


def _status_code(response: Any, error: Exception) -> int | None:
    candidate = response
    if candidate is None:
        candidate = getattr(error, "response", None)
    value = getattr(candidate, "status_code", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _retry_after_seconds(response: Any, *, now: datetime | None = None) -> float | None:
    """Parse an RFC Retry-After value and clamp it to the reviewed sleep bound."""
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    raw_value = headers.get("Retry-After")
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    if not value or len(value) > 128:
        return None
    if value.isascii() and value.isdigit():
        return float(min(int(value), int(USFWS_RETRY_MAX_SECONDS)))
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        return None
    delay = (retry_at.astimezone(UTC) - (now or datetime.now(UTC))).total_seconds()
    return min(max(delay, 0.0), USFWS_RETRY_MAX_SECONDS)


def _retry_delay_seconds(attempt: int, response: Any) -> float:
    backoff = min(
        USFWS_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
        USFWS_RETRY_MAX_SECONDS,
    )
    retry_after = _retry_after_seconds(response)
    return min(max(backoff, retry_after or 0.0), USFWS_RETRY_MAX_SECONDS)


def _get_with_retry(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    max_attempts: int,
    maximum_body_bytes: int | None = None,
    body_label: str = "body",
) -> Any:
    for attempt in range(1, max_attempts + 1):
        response: Any = None
        try:
            response = _http_get(
                url,
                headers={"Accept": "application/json, text/html", "User-Agent": USFWS_USER_AGENT},
                params=dict(params) if params is not None else None,
                timeout=USFWS_REQUEST_TIMEOUT_SECONDS,
                stream=True,
            )
            response.raise_for_status()
            if maximum_body_bytes is not None:
                try:
                    return _bounded_response_body(
                        response,
                        maximum_bytes=maximum_body_bytes,
                        label=body_label,
                    )
                finally:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
            return response
        except _ResponseBodyValidationError:
            raise
        except Exception as exc:  # requests and fixture transports expose different errors
            status_code = _status_code(response, exc)
            # A body-stream failure after a successful status is transport-like
            # and may be retried. Oversized bodies are handled above and never
            # retried because another copy cannot make them safe to parse.
            transient = (
                status_code is None
                or status_code == 429
                or status_code >= 500
                or (maximum_body_bytes is not None and 200 <= status_code < 300)
            )
            if not transient:
                raise RuntimeError(
                    f"USFWS request failed with non-retriable HTTP status {status_code}"
                ) from None
            if attempt < max_attempts:
                retry_response = response
                if retry_response is None:
                    retry_response = getattr(exc, "response", None)
                time.sleep(_retry_delay_seconds(attempt, retry_response))
                continue
            raise _RequestRetriesExhaustedError(
                f"USFWS transient request failed after {max_attempts} attempts"
            ) from None
    raise AssertionError("USFWS retry loop did not execute")


def _search_params(target: TargetSpecies) -> tuple[tuple[str, str, dict[str, Any]], ...]:
    return (
        (
            "species_facet",
            USFWS_IMAGE_SEARCH_URL,
            {
                # The FWS image search declares this filter as selectMultiple
                # and expects its contextual value as a JSON array string.
                # A scalar is silently ignored and returns the unfiltered
                # catalog, so keep this exact representation under test.
                "species": json.dumps([target.common_name], separators=(",", ":")),
                "$orderby": "field_document_publication_date desc",
            },
        ),
        (
            "exact_common_name",
            USFWS_GLOBAL_SEARCH_URL,
            {
                "$keywords": f'"{target.common_name}"',
                "type": json.dumps(["Image"], separators=(",", ":")),
                "$orderby": "search_api_relevance desc",
            },
        ),
        (
            "exact_scientific_name",
            USFWS_GLOBAL_SEARCH_URL,
            {
                "$keywords": f'"{target.scientific_name}"',
                "type": json.dumps(["Image"], separators=(",", ":")),
                "$orderby": "search_api_relevance desc",
            },
        ),
    )


def _fetch_search(
    endpoint: str,
    params: Mapping[str, Any],
    *,
    max_images: int,
    max_attempts: int,
    expected_facet: tuple[str, str],
) -> list[_SearchCandidate]:
    offset = 0
    cards: list[_SearchCandidate] = []
    expected_total: int | None = None
    while True:
        page_params = {**params, "$top": USFWS_PAGE_SIZE, "$skip": offset}
        response_body = _get_with_retry(
            endpoint,
            params=page_params,
            max_attempts=max_attempts,
            maximum_body_bytes=USFWS_MAX_SEARCH_RESPONSE_BYTES,
            body_label="search",
        )
        try:
            payload = json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("USFWS search response is not valid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("USFWS search returned a non-object JSON payload")
        fragments = payload.get("list")
        metadata = payload.get("_meta")
        if not isinstance(fragments, list) or not isinstance(metadata, dict):
            raise RuntimeError("USFWS search response is missing list or _meta")
        total = metadata.get("total")
        if not isinstance(total, int) or total < 0:
            raise RuntimeError("USFWS search response has an invalid total")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise RuntimeError("USFWS search total changed during pagination")
        if total > max_images:
            raise RuntimeError(
                f"USFWS query returned {total} images, above the full-snapshot cap of {max_images}"
            )
        if total > 0:
            facet_name, facet_value = expected_facet
            facets = metadata.get("facets")
            facet_rows = facets.get(facet_name) if isinstance(facets, dict) else None
            facet_count = (
                next(
                    (
                        row.get("count")
                        for row in facet_rows
                        if isinstance(row, dict) and row.get("filter") == facet_value
                    ),
                    None,
                )
                if isinstance(facet_rows, list)
                else None
            )
            if facet_count != total:
                raise RuntimeError(
                    "USFWS search response did not prove that its requested "
                    f"{facet_name} filter was applied"
                )
        if any(not isinstance(fragment, str) for fragment in fragments):
            raise RuntimeError("USFWS search list contains a non-HTML value")
        cards.extend(parse_search_card(fragment) for fragment in fragments)
        if len(cards) > total:
            raise RuntimeError("USFWS search returned more rows than its declared total")
        if len(cards) == total:
            break
        if not fragments:
            raise RuntimeError("USFWS search pagination ended before its declared total")
        offset += len(fragments)
    if expected_total is None or len(cards) != expected_total:
        raise RuntimeError("USFWS search did not return its complete declared snapshot")
    return cards


def _candidate_dict(candidate: _SearchCandidate) -> dict[str, Any]:
    return {
        "media_id": candidate.media_id,
        "discovery_method": ",".join(sorted(candidate.discovery_methods)),
        "source_page_url": candidate.source_page_url,
        "search_result_page_href": candidate.page_href,
        "search_result_title": candidate.title,
        "search_result_caption": candidate.caption,
        "search_result_credit": candidate.credit,
        "search_result_image_url": candidate.image_url,
        "search_result_alt_text": candidate.alt_text,
        "search_result_width": candidate.width,
        "search_result_height": candidate.height,
        "search_result_published_at": candidate.published_at,
        "search_result_mime_label": candidate.mime_label,
        "_search_endpoint": ",".join(sorted(candidate.discovery_endpoints)),
    }


def _fetch_snapshot(
    targets: tuple[TargetSpecies, ...],
    *,
    run_id: str,
    loaded_at: str,
    max_images_per_target: int,
    max_attempts: int,
    detail_workers: int,
) -> _Snapshot:
    started_at = datetime.now(UTC).isoformat()
    target_candidates: dict[str, dict[str, _SearchCandidate]] = {}
    target_by_code = {target.species_code: target for target in targets}
    candidate_record_count = 0
    for target_index, target in enumerate(targets, start=1):
        candidates: dict[str, _SearchCandidate] = {}
        for method, endpoint, params in _search_params(target):
            expected_facet = (
                ("species", target.common_name) if method == "species_facet" else ("type", "Image")
            )
            for card in _fetch_search(
                endpoint,
                params,
                max_images=max_images_per_target,
                max_attempts=max_attempts,
                expected_facet=expected_facet,
            ):
                existing = candidates.get(card.source_page_url)
                if existing is None:
                    existing = card
                    candidates[card.source_page_url] = existing
                existing.discovery_methods.add(method)
                existing.discovery_endpoints.add(endpoint)
        if len(candidates) > max_images_per_target:
            raise RuntimeError(
                f"USFWS target {target.species_code} exceeds the full-snapshot image cap"
            )
        candidate_record_count += len(candidates)
        if candidate_record_count > USFWS_MAX_TOTAL_CANDIDATES:
            raise RuntimeError(
                "USFWS snapshot exceeds the reviewed global candidate cap of "
                f"{USFWS_MAX_TOTAL_CANDIDATES}"
            )
        target_candidates[target.species_code] = candidates
        if target_index % 10 == 0 or target_index == len(targets):
            log.info(
                "snapshot_search_progress",
                completed_targets=target_index,
                total_targets=len(targets),
                candidate_records=candidate_record_count,
            )

    safe_urls = sorted(
        {
            candidate.source_page_url
            for candidates in target_candidates.values()
            for candidate in candidates.values()
            if _safe_media_page_url(candidate.source_page_url)
        }
    )
    if len(safe_urls) > USFWS_MAX_DETAIL_PAGES:
        raise RuntimeError(
            f"USFWS snapshot exceeds the reviewed detail-page cap of {USFWS_MAX_DETAIL_PAGES}"
        )
    details: dict[str, dict[str, Any]] = {}
    unavailable_detail_count = 0

    def fetch_detail(url: str) -> tuple[str, dict[str, Any]]:
        try:
            response_body = _get_with_retry(
                url,
                max_attempts=max_attempts,
                maximum_body_bytes=USFWS_MAX_DETAIL_RESPONSE_BYTES,
                body_label="detail",
            )
        except _RequestRetriesExhaustedError:
            return url, {
                "detail_fetch_status": "unavailable_after_retries",
                "scientific_name_tags_json": "[]",
                "species_tag_urls_json": "[]",
                "subject_tags_json": "[]",
            }
        try:
            html = response_body.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise RuntimeError("USFWS detail response is not valid UTF-8") from None
        return url, parse_media_page(html)

    with ThreadPoolExecutor(max_workers=detail_workers, thread_name_prefix="usfws-media") as pool:
        futures = {pool.submit(fetch_detail, url): url for url in safe_urls}
        for future in as_completed(futures):
            url, parsed = future.result()
            if parsed.get("detail_fetch_status") == "unavailable_after_retries":
                unavailable_detail_count += 1
                if unavailable_detail_count > USFWS_MAX_UNAVAILABLE_DETAILS:
                    raise RuntimeError(
                        "USFWS snapshot exceeds the reviewed unavailable detail-page cap of "
                        f"{USFWS_MAX_UNAVAILABLE_DETAILS}"
                    )
            details[url] = parsed

    records: list[dict[str, Any]] = []
    for species_code in sorted(target_candidates):
        target = target_by_code[species_code]
        for source_page_url, candidate in sorted(target_candidates[species_code].items()):
            detail = details.get(source_page_url)
            if detail is None:
                detail = {
                    "detail_fetch_status": "skipped_unsafe_url",
                    "scientific_name_tags_json": "[]",
                    "species_tag_urls_json": "[]",
                    "subject_tags_json": "[]",
                }
            records.append(
                {
                    "run_id": run_id,
                    "species_code": target.species_code,
                    "target_common_name": target.common_name,
                    "target_scientific_name": target.scientific_name,
                    **_candidate_dict(candidate),
                    **detail,
                    "_loaded_at": loaded_at,
                }
            )

    completed_at = datetime.now(UTC).isoformat()
    run = {
        "run_id": run_id,
        "status": "complete",
        "target_species_count": len(targets),
        "completed_target_species_count": len(targets),
        "record_count": len(records),
        "started_at": started_at,
        "completed_at": completed_at,
        "search_endpoint": json.dumps(
            [USFWS_IMAGE_SEARCH_URL, USFWS_GLOBAL_SEARCH_URL], separators=(",", ":")
        ),
        "page_size": USFWS_PAGE_SIZE,
        "max_images_per_target": max_images_per_target,
        "request_max_attempts": max_attempts,
        "detail_worker_count": detail_workers,
        "_loaded_at": loaded_at,
    }
    return _Snapshot(run=run, records=tuple(records))


@dlt.source
def usfws_source(
    target_species: Sequence[Mapping[str, str]] | None = None,
    max_images_per_target: int = USFWS_MAX_IMAGES_PER_TARGET,
    request_max_attempts: int = USFWS_REQUEST_MAX_ATTEMPTS,
    detail_workers: int = USFWS_DETAIL_WORKERS,
    run_id: str | None = None,
    loaded_at: str | None = None,
) -> Any:
    """Return a complete USFWS image-metadata snapshot for explicit targets.

    No network call is made at source construction time. Callers must supply
    target species before iterating either resource. A run marker is emitted
    only after every bounded search page and safe media detail page succeeds.
    """
    targets = _normalize_targets(target_species)
    if not 1 <= max_images_per_target <= USFWS_MAX_IMAGES_PER_TARGET:
        raise ValueError(
            f"USFWS max_images_per_target must be between 1 and {USFWS_MAX_IMAGES_PER_TARGET}"
        )
    if not 1 <= request_max_attempts <= USFWS_REQUEST_MAX_ATTEMPTS:
        raise ValueError(
            f"USFWS request_max_attempts must be between 1 and {USFWS_REQUEST_MAX_ATTEMPTS}"
        )
    if not 1 <= detail_workers <= USFWS_MAX_DETAIL_WORKERS:
        raise ValueError(f"USFWS detail_workers must be between 1 and {USFWS_MAX_DETAIL_WORKERS}")
    effective_loaded_at = loaded_at or pendulum.now("UTC").isoformat()
    target_identity = [(target.species_code, target.scientific_name) for target in targets]
    effective_run_id = (
        run_id or hashlib.sha256(f"{effective_loaded_at}|{target_identity}".encode()).hexdigest()
    )
    cached: _Snapshot | None = None
    cache_lock = threading.Lock()

    def snapshot() -> _Snapshot:
        nonlocal cached
        if not targets:
            raise ValueError("USFWS target_species must be supplied by the snapshot caller")
        if cached is None:
            with cache_lock:
                if cached is None:
                    cached = _fetch_snapshot(
                        targets,
                        run_id=effective_run_id,
                        loaded_at=effective_loaded_at,
                        max_images_per_target=max_images_per_target,
                        max_attempts=request_max_attempts,
                        detail_workers=detail_workers,
                    )
        return cached

    @dlt.resource(
        primary_key="run_id",
        write_disposition="merge",
        columns=_RUN_COLUMNS,
    )
    def image_search_runs() -> Iterator[dict[str, Any]]:
        yield snapshot().run

    @dlt.resource(
        primary_key=["run_id", "species_code", "source_page_url"],
        write_disposition="merge",
        columns=_IMAGE_COLUMNS,
    )
    def image_records() -> Iterator[dict[str, Any]]:
        yield from snapshot().records

    return [image_search_runs, image_records]
