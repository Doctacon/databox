"""Human, species-scoped selection policy for Rufous's prepared bird media.

Preparation proves that an object is well formed, licensed, bounded, and tied
to reviewed metadata.  It cannot prove what the pixels depict.  Production
therefore uses a committed human decision ledger keyed by species and the
SHA-256 of the final WebP bytes.

Exactly one current selection is required for every species represented by the
prepared manifest.  Other prepared candidates are implicit exclusions: they do
not need approval, cannot block the gate merely by being unreviewed, and are
never exported or published.  Explicit rejections remain in the ledger as an
audit trail, including the three disqualifiers that Rufous never publishes:
dead birds, humans in frame, and migration maps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

APPROVAL_SCHEMA_VERSION = 2
APPROVAL_MODE = "rufous-media-human-species-selections"
REVIEW_POLICY = "one-live-bird-image-per-species-v1"
SELECTION_REASON = "live_bird_without_human_or_migration_map"
REJECTION_REASONS = frozenset({"dead_bird", "human_present", "migration_map", "other"})
DISQUALIFYING_REJECTION_REASONS = REJECTION_REASONS - {"other"}
NO_SAFE_IMAGE_REASONS = frozenset({"no_compliant_candidate", "user_content_policy"})
LOCAL_DECISION_MODE = "rufous-media-local-review-decisions-not-selections"
LOCAL_REVIEW_MARKER = "RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY"
MAX_APPROVAL_BYTES = 25 * 1024 * 1024
MAX_APPROVALS = 20_000
DEFAULT_APPROVAL_PATH = Path("config/rufous-media-visual-approvals.json")

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SCIENTIFIC_NAME = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+(?: [A-Za-z-]+)?$")
_USFWS_MEDIA_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_MEDIA_PAGE = re.compile(r"^https://www\.inaturalist\.org/photos/[1-9][0-9]*$")
_PUBLIC_MEDIA_URL = re.compile(
    r"^https://rufous-data\.loughondata\.com/rufous-media/v1/objects/"
    r"(?P<shard>[a-f0-9]{2})/(?P<sha>[a-f0-9]{64})\.webp$"
)
_MEDIA_PROVIDERS = frozenset({"usfws", "inaturalist"})
_REVIEWER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@+'-]{1,99}$")
_LEDGER_KEYS = {
    "schema_version",
    "mode",
    "review_policy",
    "selections",
    "rejections",
    "species_exclusions",
}
_SELECTION_KEYS = {
    "sha256",
    "decision",
    "reason",
    "reviewed_at",
    "reviewed_by",
    "scientific_name",
    "source_page_urls",
}
_REJECTION_KEYS = _SELECTION_KEYS
_SPECIES_EXCLUSION_KEYS = {
    "scientific_name",
    "decision",
    "reason",
    "reviewed_at",
    "reviewed_by",
    "candidates",
}
_EXCLUDED_CANDIDATE_KEYS = {"sha256", "source_page_urls"}
_LOCAL_PAYLOAD_KEYS = {
    "schema_version",
    "mode",
    "marker",
    "source_manifest_sha256",
    "decisions",
    "species_exclusions",
}
_LOCAL_DECISION_KEYS = {
    "sha256",
    "decision",
    "reason",
    "scientific_name",
    "source_page_urls",
}
_LOCAL_SPECIES_EXCLUSION_KEYS = {
    "scientific_name",
    "decision",
    "reason",
    "candidates",
}


class MediaApprovalError(RuntimeError):
    """Prepared media does not have valid committed human selection."""


@dataclass(frozen=True)
class MediaCandidate:
    scientific_name: str
    sha256: str
    source_page_urls: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        return self.scientific_name.casefold(), self.sha256


@dataclass(frozen=True)
class VisualSelection:
    sha256: str
    decision: str
    reason: str
    reviewed_at: str
    reviewed_by: str
    scientific_name: str
    source_page_urls: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        return self.scientific_name.casefold(), self.sha256


@dataclass(frozen=True)
class VisualRejection:
    sha256: str
    decision: str
    reason: str
    reviewed_at: str
    reviewed_by: str
    scientific_name: str
    source_page_urls: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        return self.scientific_name.casefold(), self.sha256


@dataclass(frozen=True)
class ExcludedCandidate:
    sha256: str
    source_page_urls: tuple[str, ...]


@dataclass(frozen=True)
class SpeciesExclusion:
    scientific_name: str
    decision: str
    reason: str
    reviewed_at: str
    reviewed_by: str
    candidates: tuple[ExcludedCandidate, ...]


@dataclass(frozen=True)
class VisualDecisionLedger:
    selections: tuple[VisualSelection, ...]
    rejections: tuple[VisualRejection, ...]
    species_exclusions: tuple[SpeciesExclusion, ...]


@dataclass(frozen=True)
class ApprovalSummary:
    manifest_candidates: int
    manifest_species: int
    selected_species: int
    selected_objects: int
    excluded_species: int
    explicit_rejections: int
    ledger_decisions: int
    unused_ledger_decisions: int


@dataclass(frozen=True)
class ApprovedMediaPlan:
    summary: ApprovalSummary
    selections: tuple[VisualSelection, ...]
    species_exclusions: tuple[SpeciesExclusion, ...]

    @property
    def selected_sha256s(self) -> frozenset[str]:
        return frozenset(item.sha256 for item in self.selections)

    @property
    def selected_sha256_by_species(self) -> dict[str, str]:
        return {item.scientific_name.casefold(): item.sha256 for item in self.selections}

    @property
    def excluded_species(self) -> frozenset[str]:
        return frozenset(item.scientific_name.casefold() for item in self.species_exclusions)


def canonical_approval_json(payload: object) -> bytes:
    """Return the sole accepted, review-friendly representation of a ledger."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def empty_approval_ledger() -> dict[str, object]:
    """Return a valid ledger that intentionally selects no media."""
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "mode": APPROVAL_MODE,
        "review_policy": REVIEW_POLICY,
        "selections": [],
        "rejections": [],
        "species_exclusions": [],
    }


def load_visual_approvals(path: Path) -> dict[str, VisualSelection]:
    """Load current selections, keyed by normalized scientific name.

    The historical function name is retained because the workflow and callers
    still refer to the committed file as the visual-approval ledger.
    """
    ledger = _load_visual_decisions(path)
    return {item.scientific_name.casefold(): item for item in ledger.selections}


def load_visual_rejections(path: Path) -> dict[tuple[str, str], VisualRejection]:
    """Load explicit species/hash rejections from the committed ledger."""
    ledger = _load_visual_decisions(path)
    return {item.key: item for item in ledger.rejections}


def _load_visual_decisions(path: Path) -> VisualDecisionLedger:
    raw = _read_json_bytes(path, label="visual-decision ledger")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MediaApprovalError("visual-decision ledger is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict) or set(payload) != _LEDGER_KEYS:
        raise MediaApprovalError("visual-decision ledger has unexpected fields")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != APPROVAL_SCHEMA_VERSION
        or payload.get("mode") != APPROVAL_MODE
        or payload.get("review_policy") != REVIEW_POLICY
    ):
        raise MediaApprovalError("visual-decision ledger has an unsupported contract")
    if raw != canonical_approval_json(payload):
        raise MediaApprovalError("visual-decision ledger must use canonical sorted JSON")

    raw_selections = payload.get("selections")
    raw_rejections = payload.get("rejections")
    raw_species_exclusions = payload.get("species_exclusions")
    if (
        not isinstance(raw_selections, list)
        or not isinstance(raw_rejections, list)
        or not isinstance(raw_species_exclusions, list)
        or len(raw_selections) + len(raw_rejections) + len(raw_species_exclusions) > MAX_APPROVALS
    ):
        raise MediaApprovalError("visual-decision ledger has an invalid decision list")

    selections: list[VisualSelection] = []
    previous_selection: tuple[str, str] | None = None
    selected_species: set[str] = set()
    for index, row in enumerate(raw_selections):
        parsed = _parse_decision_row(row, index=index, expected="selected")
        assert isinstance(parsed, VisualSelection)
        sort_key = parsed.key
        if previous_selection is not None and sort_key <= previous_selection:
            raise MediaApprovalError("visual selections must be uniquely sorted by species/hash")
        previous_selection = sort_key
        species_key = parsed.scientific_name.casefold()
        if species_key in selected_species:
            raise MediaApprovalError("visual ledger may select only one image per species")
        selected_species.add(species_key)
        selections.append(parsed)

    rejections: list[VisualRejection] = []
    previous_rejection: tuple[str, str] | None = None
    selection_keys = {item.key for item in selections}
    for index, row in enumerate(raw_rejections):
        parsed = _parse_decision_row(row, index=index, expected="rejected")
        assert isinstance(parsed, VisualRejection)
        if previous_rejection is not None and parsed.key <= previous_rejection:
            raise MediaApprovalError("visual rejections must be uniquely sorted by species/hash")
        previous_rejection = parsed.key
        if parsed.key in selection_keys:
            raise MediaApprovalError("one candidate cannot be both selected and rejected")
        rejections.append(parsed)
    species_exclusions: list[SpeciesExclusion] = []
    previous_species = ""
    for index, row in enumerate(raw_species_exclusions):
        exclusion = _parse_species_exclusion(row, index=index)
        species_key = exclusion.scientific_name.casefold()
        if species_key <= previous_species:
            raise MediaApprovalError("species exclusions must be uniquely sorted by species")
        previous_species = species_key
        if species_key in selected_species:
            raise MediaApprovalError("one species cannot be both selected and excluded")
        species_exclusions.append(exclusion)
    return VisualDecisionLedger(tuple(selections), tuple(rejections), tuple(species_exclusions))


def _parse_decision_row(
    row: object,
    *,
    index: int,
    expected: str,
) -> VisualSelection | VisualRejection:
    if not isinstance(row, dict) or set(row) != _SELECTION_KEYS:
        raise MediaApprovalError(f"visual {expected} decision {index} has unexpected fields")
    sha256 = row.get("sha256")
    scientific_name = row.get("scientific_name")
    reviewed_at = row.get("reviewed_at")
    reviewed_by = row.get("reviewed_by")
    reason = row.get("reason")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise MediaApprovalError(f"visual {expected} decision {index} has an invalid SHA-256")
    if not isinstance(scientific_name, str) or not _SCIENTIFIC_NAME.fullmatch(scientific_name):
        raise MediaApprovalError(
            f"visual {expected} decision {index} has an invalid scientific name"
        )
    source_pages = _strict_media_source_pages(
        row.get("source_page_urls"),
        label=f"visual {expected} decision {index} source_page_urls",
    )
    if row.get("decision") != expected:
        raise MediaApprovalError(f"visual {expected} decision {index} has the wrong decision")
    if expected == "selected" and reason != SELECTION_REASON:
        raise MediaApprovalError(
            f"visual selection {index} lacks the live-bird content attestation"
        )
    if expected == "rejected" and reason not in REJECTION_REASONS:
        raise MediaApprovalError(f"visual rejection {index} has an invalid reason")
    if not isinstance(reviewed_at, str) or not _valid_review_date(reviewed_at):
        raise MediaApprovalError(f"visual {expected} decision {index} has an invalid review date")
    if not isinstance(reviewed_by, str) or not _REVIEWER.fullmatch(reviewed_by):
        raise MediaApprovalError(f"visual {expected} decision {index} has an invalid reviewer")
    assert isinstance(reason, str)
    if expected == "selected":
        return VisualSelection(
            sha256=sha256,
            decision=expected,
            reason=reason,
            reviewed_at=reviewed_at,
            reviewed_by=reviewed_by,
            scientific_name=scientific_name,
            source_page_urls=source_pages,
        )
    return VisualRejection(
        sha256=sha256,
        decision=expected,
        reason=reason,
        reviewed_at=reviewed_at,
        reviewed_by=reviewed_by,
        scientific_name=scientific_name,
        source_page_urls=source_pages,
    )


def _parse_species_exclusion(row: object, *, index: int) -> SpeciesExclusion:
    if not isinstance(row, dict) or set(row) != _SPECIES_EXCLUSION_KEYS:
        raise MediaApprovalError(f"species exclusion {index} has unexpected fields")
    scientific_name = row.get("scientific_name")
    reviewed_at = row.get("reviewed_at")
    reviewed_by = row.get("reviewed_by")
    reason = row.get("reason")
    if not isinstance(scientific_name, str) or not _SCIENTIFIC_NAME.fullmatch(scientific_name):
        raise MediaApprovalError(f"species exclusion {index} has an invalid scientific name")
    if row.get("decision") != "no_safe_image" or reason not in NO_SAFE_IMAGE_REASONS:
        raise MediaApprovalError(f"species exclusion {index} has an invalid decision or reason")
    if not isinstance(reviewed_at, str) or not _valid_review_date(reviewed_at):
        raise MediaApprovalError(f"species exclusion {index} has an invalid review date")
    if not isinstance(reviewed_by, str) or not _REVIEWER.fullmatch(reviewed_by):
        raise MediaApprovalError(f"species exclusion {index} has an invalid reviewer")
    candidates = _parse_excluded_candidates(
        row.get("candidates"), label=f"species exclusion {index} candidates"
    )
    assert isinstance(reason, str)
    return SpeciesExclusion(
        scientific_name=scientific_name,
        decision="no_safe_image",
        reason=reason,
        reviewed_at=reviewed_at,
        reviewed_by=reviewed_by,
        candidates=candidates,
    )


def _parse_excluded_candidates(value: object, *, label: str) -> tuple[ExcludedCandidate, ...]:
    if not isinstance(value, list) or not value or len(value) > MAX_APPROVALS:
        raise MediaApprovalError(f"{label} must be a nonempty bounded list")
    parsed: list[ExcludedCandidate] = []
    previous_hash = ""
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != _EXCLUDED_CANDIDATE_KEYS:
            raise MediaApprovalError(f"{label} item {index} has unexpected fields")
        sha256 = row.get("sha256")
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise MediaApprovalError(f"{label} item {index} has invalid SHA-256")
        if sha256 <= previous_hash:
            raise MediaApprovalError(f"{label} must be uniquely sorted by SHA-256")
        previous_hash = sha256
        pages = _strict_media_source_pages(
            row.get("source_page_urls"),
            label=f"{label} item {index} source_page_urls",
        )
        parsed.append(ExcludedCandidate(sha256=sha256, source_page_urls=pages))
    return tuple(parsed)


def load_manifest_provenance(
    path: Path,
    *,
    provider: str | None = None,
) -> dict[tuple[str, str], MediaCandidate]:
    """Read species/hash candidates and exact source provenance from a manifest.

    A provider scope is an exact manifest contract, not a filter: every item
    must identify that provider.  This prevents a mixed preparation from being
    mistaken for a small provider-only release.
    """
    if provider is not None and provider not in _MEDIA_PROVIDERS:
        raise MediaApprovalError("media provider scope is not reviewed")
    raw = _read_json_bytes(path, label="prepared-media manifest")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MediaApprovalError("prepared-media manifest is not valid UTF-8 JSON") from None
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("mode") != "rufous-media-preparation"
    ):
        raise MediaApprovalError("prepared-media manifest has an unsupported contract")
    items = payload.get("items")
    if not isinstance(items, list) or not items or len(items) > MAX_APPROVALS:
        raise MediaApprovalError("prepared-media manifest has an invalid reviewable item list")

    pages_by_candidate: dict[tuple[str, str], set[str]] = defaultdict(set)
    object_hashes: set[str] = set()
    species: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise MediaApprovalError(f"prepared-media item {index} is malformed")
        sha256 = item.get("sha256")
        scientific_name = item.get("scientific_name")
        source_page_url = item.get("source_page_url")
        item_provider = item.get("provider", "usfws")
        url = item.get("url")
        match = _PUBLIC_MEDIA_URL.fullmatch(url) if isinstance(url, str) else None
        if (
            not isinstance(sha256, str)
            or not _SHA256.fullmatch(sha256)
            or not isinstance(scientific_name, str)
            or not _SCIENTIFIC_NAME.fullmatch(scientific_name)
            or not isinstance(source_page_url, str)
            or not _valid_source_page(item_provider, source_page_url)
            or match is None
            or match.group("sha") != sha256
            or match.group("shard") != sha256[:2]
        ):
            raise MediaApprovalError(f"prepared-media item {index} has invalid provenance")
        if provider is not None and item_provider != provider:
            raise MediaApprovalError(
                "prepared-media manifest contains media outside the requested "
                f"{provider} provider scope"
            )
        key = (scientific_name.casefold(), sha256)
        pages_by_candidate[key].add(source_page_url)
        object_hashes.add(sha256)
        species.add(scientific_name.casefold())

    counts = payload.get("counts")
    if (
        not isinstance(counts, dict)
        or type(counts.get("items")) is not int
        or counts.get("items") != len(items)
        or type(counts.get("objects")) is not int
        or counts.get("objects") != len(object_hashes)
        or type(counts.get("species")) is not int
        or counts.get("species") != len(species)
    ):
        raise MediaApprovalError("prepared-media manifest counts do not match review provenance")

    canonical_names: dict[str, str] = {}
    for item in items:
        assert isinstance(item, dict)
        name = item["scientific_name"]
        assert isinstance(name, str)
        canonical_names[name.casefold()] = name
    return {
        key: MediaCandidate(
            scientific_name=canonical_names[key[0]],
            sha256=key[1],
            source_page_urls=tuple(sorted(pages)),
        )
        for key, pages in sorted(pages_by_candidate.items())
    }


def _valid_source_page(provider: object, source_page_url: str) -> bool:
    if provider == "usfws":
        return _USFWS_MEDIA_PAGE.fullmatch(source_page_url) is not None
    if provider == "inaturalist":
        return _INATURALIST_MEDIA_PAGE.fullmatch(source_page_url) is not None
    return False


def require_visual_approvals(
    manifest_path: Path,
    approval_path: Path,
    *,
    provider: str | None = None,
) -> ApprovedMediaPlan:
    """Require one selection or explicit no-safe-image exclusion per species.

    A provider-scoped manifest uses only decisions tied to that provider and
    permits the complete ledger to retain decisions for other releases.  The
    unscoped production gate keeps its stricter whole-manifest behavior.
    """
    candidates = load_manifest_provenance(manifest_path, provider=provider)
    complete_ledger = _load_visual_decisions(approval_path)
    ledger = complete_ledger
    if provider is not None:
        ledger = _ledger_for_provider(ledger, provider=provider)
    candidates_by_species: dict[str, list[MediaCandidate]] = defaultdict(list)
    for candidate in candidates.values():
        candidates_by_species[candidate.scientific_name.casefold()].append(candidate)

    selection_by_species = {item.scientific_name.casefold(): item for item in ledger.selections}
    exclusion_by_species = {
        item.scientific_name.casefold(): item for item in ledger.species_exclusions
    }
    missing_species = sorted(
        set(candidates_by_species) - set(selection_by_species) - set(exclusion_by_species)
    )
    if missing_species:
        raise MediaApprovalError(
            f"{len(missing_species)} represented species lack a committed human image "
            "selection or no-safe-image exclusion; first missing species: "
            f"{missing_species[0]}"
        )
    absent_selections = sorted(set(selection_by_species) - set(candidates_by_species))
    if absent_selections:
        selected = selection_by_species[absent_selections[0]]
        raise MediaApprovalError(
            "committed selected media is absent from the current prepared manifest for "
            f"{selected.scientific_name}"
        )

    current_selections: list[VisualSelection] = []
    for species_key in sorted(set(candidates_by_species).intersection(selection_by_species)):
        selected = selection_by_species[species_key]
        current = candidates.get(selected.key)
        if current is None:
            raise MediaApprovalError(
                f"selected pixels are not a current candidate for {selected.scientific_name}"
            )
        if not set(current.source_page_urls).issubset(selected.source_page_urls):
            raise MediaApprovalError(
                "selected media provenance exceeds its committed human decision for "
                f"{selected.scientific_name} / SHA-256 {selected.sha256}"
            )
        current_selections.append(selected)

    current_exclusions: list[SpeciesExclusion] = []
    for species_key in sorted(set(candidates_by_species).intersection(exclusion_by_species)):
        exclusion = exclusion_by_species[species_key]
        current_candidates = tuple(
            ExcludedCandidate(
                sha256=item.sha256,
                source_page_urls=item.source_page_urls,
            )
            for item in sorted(candidates_by_species[species_key], key=lambda item: item.sha256)
        )
        if exclusion.candidates != current_candidates:
            raise MediaApprovalError(
                "no-safe-image exclusion does not match every current candidate for "
                f"{exclusion.scientific_name}"
            )
        current_exclusions.append(exclusion)

    disqualified_hashes = {
        item.sha256
        for item in complete_ledger.rejections
        if item.reason in DISQUALIFYING_REJECTION_REASONS
    }
    conflicting = sorted(
        {item.sha256 for item in current_selections}.intersection(disqualified_hashes)
    )
    if conflicting:
        raise MediaApprovalError(
            "selected pixels also carry a dead-bird, human-present, or migration-map "
            f"rejection: {conflicting[0]}"
        )

    current_keys = set(candidates)
    used_rejections = sum(item.key in current_keys for item in ledger.rejections)
    unused_selections = len(set(selection_by_species) - set(candidates_by_species))
    unused_exclusions = len(set(exclusion_by_species) - set(candidates_by_species))
    summary = ApprovalSummary(
        manifest_candidates=len(candidates),
        manifest_species=len(candidates_by_species),
        selected_species=len(current_selections),
        selected_objects=len({item.sha256 for item in current_selections}),
        excluded_species=len(current_exclusions),
        explicit_rejections=used_rejections,
        ledger_decisions=(
            len(ledger.selections) + len(ledger.rejections) + len(ledger.species_exclusions)
        ),
        unused_ledger_decisions=(
            unused_selections + unused_exclusions + len(ledger.rejections) - used_rejections
        ),
    )
    return ApprovedMediaPlan(
        summary=summary,
        selections=tuple(current_selections),
        species_exclusions=tuple(current_exclusions),
    )


def _ledger_for_provider(
    ledger: VisualDecisionLedger,
    *,
    provider: str,
) -> VisualDecisionLedger:
    """Return the fully parsed ledger decisions applicable to one provider."""
    selections = tuple(
        item for item in ledger.selections if _pages_provider(item.source_page_urls) == provider
    )
    rejections = tuple(
        item for item in ledger.rejections if _pages_provider(item.source_page_urls) == provider
    )
    exclusions: list[SpeciesExclusion] = []
    for exclusion in ledger.species_exclusions:
        candidates = tuple(
            item
            for item in exclusion.candidates
            if _pages_provider(item.source_page_urls) == provider
        )
        if candidates:
            exclusions.append(replace(exclusion, candidates=candidates))
    return VisualDecisionLedger(selections, rejections, tuple(exclusions))


def _pages_provider(source_page_urls: tuple[str, ...]) -> str:
    """Return the provider already proven by strict ledger parsing."""
    first = source_page_urls[0]
    if _USFWS_MEDIA_PAGE.fullmatch(first):
        return "usfws"
    if _INATURALIST_MEDIA_PAGE.fullmatch(first):
        return "inaturalist"
    raise MediaApprovalError("media decision contains an unreviewed provider")


def review_candidates(manifest_path: Path, approval_path: Path) -> dict[str, object]:
    """Build a deterministic, non-selecting list for local species review."""
    candidates = load_manifest_provenance(manifest_path)
    ledger = _load_visual_decisions(approval_path)
    selections = {item.key: item for item in ledger.selections}
    rejections = {item.key: item for item in ledger.rejections}
    objects = []
    for candidate in candidates.values():
        selected = selections.get(candidate.key)
        rejected = rejections.get(candidate.key)
        decision = "selected" if selected else "rejected" if rejected else "unreviewed"
        reason = selected.reason if selected else rejected.reason if rejected else None
        objects.append(
            {
                "sha256": candidate.sha256,
                "object_path": (f"objects/{candidate.sha256[:2]}/{candidate.sha256}.webp"),
                "scientific_name": candidate.scientific_name,
                "source_page_urls": list(candidate.source_page_urls),
                "decision": decision,
                "reason": reason,
            }
        )
    return {
        "schema_version": 2,
        "mode": "rufous-media-human-review-candidates",
        "review_policy": REVIEW_POLICY,
        "objects": objects,
        "species_exclusions": [
            _species_exclusion_as_json(item) for item in ledger.species_exclusions
        ],
    }


def write_review_candidates(
    manifest_path: Path,
    approval_path: Path,
    output_path: Path,
) -> int:
    """Atomically write local review input; never mutate the decision ledger."""
    payload = review_candidates(manifest_path, approval_path)
    _atomic_write_json(output_path, payload)
    objects = payload["objects"]
    return len(objects) if isinstance(objects, list) else 0


def merge_local_review_decisions(
    manifest_path: Path,
    approval_path: Path,
    local_decisions_path: Path,
    output_path: Path,
    *,
    reviewed_by: str,
    reviewed_at: str | None = None,
) -> ApprovalSummary:
    """Convert a gallery export into a canonical, auditable ledger update.

    The browser export is deliberately not itself an approval.  This explicit
    conversion binds each decision to the unchanged prepared manifest and adds
    reviewer/date provenance before writing a separate canonical ledger.
    """
    if not _REVIEWER.fullmatch(reviewed_by):
        raise MediaApprovalError("reviewed-by is invalid")
    review_date = reviewed_at or date.today().isoformat()
    if not _valid_review_date(review_date):
        raise MediaApprovalError("reviewed-at is invalid")
    candidates = load_manifest_provenance(manifest_path)
    ledger = _load_visual_decisions(approval_path)
    local_payload, local_species_exclusions = _load_local_decisions(
        local_decisions_path, manifest_path
    )

    selections = {item.scientific_name.casefold(): item for item in ledger.selections}
    rejections = {item.key: item for item in ledger.rejections}
    species_exclusions = {
        item.scientific_name.casefold(): item for item in ledger.species_exclusions
    }
    for row in local_payload:
        scientific_name = row["scientific_name"]
        sha256 = row["sha256"]
        decision = row["decision"]
        reason = row["reason"]
        source_page_urls = row["source_page_urls"]
        assert isinstance(scientific_name, str)
        assert isinstance(sha256, str)
        assert isinstance(decision, str)
        assert isinstance(reason, str)
        assert isinstance(source_page_urls, list)
        key = (scientific_name.casefold(), sha256)
        candidate = candidates.get(key)
        if candidate is None or list(candidate.source_page_urls) != source_page_urls:
            raise MediaApprovalError("local review decision is not a current exact candidate")
        if decision == "selected":
            species_exclusions.pop(key[0], None)
            selections[key[0]] = VisualSelection(
                sha256=key[1],
                decision="selected",
                reason=SELECTION_REASON,
                reviewed_at=review_date,
                reviewed_by=reviewed_by,
                scientific_name=candidate.scientific_name,
                source_page_urls=candidate.source_page_urls,
            )
            rejections.pop(key, None)
        else:
            selected = selections.get(key[0])
            if selected is not None and selected.sha256 == key[1]:
                selections.pop(key[0])
            rejections[key] = VisualRejection(
                sha256=key[1],
                decision="rejected",
                reason=reason,
                reviewed_at=review_date,
                reviewed_by=reviewed_by,
                scientific_name=candidate.scientific_name,
                source_page_urls=candidate.source_page_urls,
            )

    candidates_by_species: dict[str, list[MediaCandidate]] = defaultdict(list)
    for candidate in candidates.values():
        candidates_by_species[candidate.scientific_name.casefold()].append(candidate)
    for row in local_species_exclusions:
        scientific_name = row["scientific_name"]
        reason = row["reason"]
        raw_candidates = row["candidates"]
        assert isinstance(scientific_name, str)
        assert isinstance(reason, str)
        assert isinstance(raw_candidates, list)
        species_key = scientific_name.casefold()
        current = candidates_by_species.get(species_key)
        if not current:
            raise MediaApprovalError("local no-safe-image exclusion has no current species")
        expected = tuple(
            ExcludedCandidate(item.sha256, item.source_page_urls)
            for item in sorted(current, key=lambda item: item.sha256)
        )
        supplied = _parse_excluded_candidates(
            raw_candidates,
            label=f"local no-safe-image exclusion for {scientific_name}",
        )
        if supplied != expected:
            raise MediaApprovalError(
                "local no-safe-image exclusion does not match every current candidate"
            )
        selections.pop(species_key, None)
        species_exclusions[species_key] = SpeciesExclusion(
            scientific_name=current[0].scientific_name,
            decision="no_safe_image",
            reason=reason,
            reviewed_at=review_date,
            reviewed_by=reviewed_by,
            candidates=expected,
        )

    payload = empty_approval_ledger()
    payload["selections"] = [
        _decision_as_json(item) for item in sorted(selections.values(), key=lambda item: item.key)
    ]
    payload["rejections"] = [
        _decision_as_json(item) for item in sorted(rejections.values(), key=lambda item: item.key)
    ]
    payload["species_exclusions"] = [
        _species_exclusion_as_json(item)
        for item in sorted(
            species_exclusions.values(), key=lambda item: item.scientific_name.casefold()
        )
    ]
    _atomic_write_json(output_path, payload)
    # Re-load the output before returning so the writer cannot emit a contract
    # the production reader would reject.
    written = _load_visual_decisions(output_path)
    current_keys = set(candidates)
    selected_current = [item for item in written.selections if item.key in current_keys]
    rejected_current = [item for item in written.rejections if item.key in current_keys]
    represented_species = {key[0] for key in candidates}
    excluded_current = [
        item
        for item in written.species_exclusions
        if item.scientific_name.casefold() in represented_species
    ]
    return ApprovalSummary(
        manifest_candidates=len(candidates),
        manifest_species=len({key[0] for key in candidates}),
        selected_species=len(selected_current),
        selected_objects=len({item.sha256 for item in selected_current}),
        excluded_species=len(excluded_current),
        explicit_rejections=len(rejected_current),
        ledger_decisions=(
            len(written.selections) + len(written.rejections) + len(written.species_exclusions)
        ),
        unused_ledger_decisions=(
            len(written.selections)
            + len(written.rejections)
            + len(written.species_exclusions)
            - len(selected_current)
            - len(rejected_current)
            - len(excluded_current)
        ),
    )


def _load_local_decisions(
    path: Path, manifest_path: Path
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw = _read_json_bytes(path, label="local review decisions")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MediaApprovalError("local review decisions are not valid UTF-8 JSON") from None
    if not isinstance(payload, dict) or set(payload) != _LOCAL_PAYLOAD_KEYS:
        raise MediaApprovalError("local review decisions have unexpected fields")
    expected_manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if (
        payload.get("schema_version") != 2
        or payload.get("mode") != LOCAL_DECISION_MODE
        or payload.get("marker") != LOCAL_REVIEW_MARKER
        or payload.get("source_manifest_sha256") != expected_manifest_hash
    ):
        raise MediaApprovalError("local review decisions do not match this prepared manifest")
    rows = payload.get("decisions")
    if not isinstance(rows, list) or len(rows) > MAX_APPROVALS:
        raise MediaApprovalError("local review decisions have an invalid decision list")
    normalized: list[dict[str, object]] = []
    previous: tuple[str, str] | None = None
    selected_species: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != _LOCAL_DECISION_KEYS:
            raise MediaApprovalError(f"local review decision {index} has unexpected fields")
        sha256 = row.get("sha256")
        scientific_name = row.get("scientific_name")
        decision = row.get("decision")
        reason = row.get("reason")
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise MediaApprovalError(f"local review decision {index} has invalid SHA-256")
        if not isinstance(scientific_name, str) or not _SCIENTIFIC_NAME.fullmatch(scientific_name):
            raise MediaApprovalError(f"local review decision {index} has invalid species")
        pages = _strict_media_source_pages(
            row.get("source_page_urls"),
            label=f"local review decision {index} source_page_urls",
        )
        if decision == "selected":
            if reason != SELECTION_REASON:
                raise MediaApprovalError(
                    f"local review selection {index} lacks the content attestation"
                )
            species_key = scientific_name.casefold()
            if species_key in selected_species:
                raise MediaApprovalError(
                    "local review decisions may select only one image per species"
                )
            selected_species.add(species_key)
        elif decision == "rejected":
            if reason not in REJECTION_REASONS:
                raise MediaApprovalError(f"local review rejection {index} has invalid reason")
        else:
            raise MediaApprovalError(f"local review decision {index} has invalid decision")
        key = (scientific_name.casefold(), sha256)
        if previous is not None and key <= previous:
            raise MediaApprovalError("local review decisions must be uniquely sorted")
        previous = key
        normalized.append(
            {
                "sha256": sha256,
                "decision": decision,
                "reason": reason,
                "scientific_name": scientific_name,
                "source_page_urls": list(pages),
            }
        )
    raw_exclusions = payload.get("species_exclusions")
    if not isinstance(raw_exclusions, list) or len(raw_exclusions) > MAX_APPROVALS:
        raise MediaApprovalError("local species exclusions have an invalid list")
    normalized_exclusions: list[dict[str, object]] = []
    previous_species = ""
    for index, row in enumerate(raw_exclusions):
        if not isinstance(row, dict) or set(row) != _LOCAL_SPECIES_EXCLUSION_KEYS:
            raise MediaApprovalError(f"local species exclusion {index} has unexpected fields")
        scientific_name = row.get("scientific_name")
        reason = row.get("reason")
        if (
            not isinstance(scientific_name, str)
            or not _SCIENTIFIC_NAME.fullmatch(scientific_name)
            or row.get("decision") != "no_safe_image"
            or reason not in NO_SAFE_IMAGE_REASONS
        ):
            raise MediaApprovalError(f"local species exclusion {index} is invalid")
        species_key = scientific_name.casefold()
        if species_key <= previous_species:
            raise MediaApprovalError("local species exclusions must be uniquely sorted")
        previous_species = species_key
        if species_key in selected_species:
            raise MediaApprovalError("local review cannot both select and exclude one species")
        candidates = _parse_excluded_candidates(
            row.get("candidates"),
            label=f"local species exclusion {index} candidates",
        )
        normalized_exclusions.append(
            {
                "scientific_name": scientific_name,
                "decision": "no_safe_image",
                "reason": reason,
                "candidates": [
                    {
                        "sha256": candidate.sha256,
                        "source_page_urls": list(candidate.source_page_urls),
                    }
                    for candidate in candidates
                ],
            }
        )
    return normalized, normalized_exclusions


def _decision_as_json(item: VisualSelection | VisualRejection) -> dict[str, object]:
    return {
        "sha256": item.sha256,
        "decision": item.decision,
        "reason": item.reason,
        "reviewed_at": item.reviewed_at,
        "reviewed_by": item.reviewed_by,
        "scientific_name": item.scientific_name,
        "source_page_urls": list(item.source_page_urls),
    }


def _species_exclusion_as_json(item: SpeciesExclusion) -> dict[str, object]:
    return {
        "scientific_name": item.scientific_name,
        "decision": item.decision,
        "reason": item.reason,
        "reviewed_at": item.reviewed_at,
        "reviewed_by": item.reviewed_by,
        "candidates": [
            {
                "sha256": candidate.sha256,
                "source_page_urls": list(candidate.source_page_urls),
            }
            for candidate in item.candidates
        ],
    }


def _atomic_write_json(output_path: Path, payload: object) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{output_path.name}-", dir=output_path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(canonical_approval_json(payload))
    try:
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json_bytes(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise MediaApprovalError(f"{label} is missing or unsafe")
    try:
        size = path.stat().st_size
    except OSError:
        raise MediaApprovalError(f"{label} could not be inspected") from None
    if size <= 0 or size > MAX_APPROVAL_BYTES:
        raise MediaApprovalError(f"{label} is empty or exceeds 25 MiB")
    try:
        return path.read_bytes()
    except OSError:
        raise MediaApprovalError(f"{label} could not be read") from None


def _strict_sorted_strings(
    value: object, *, pattern: re.Pattern[str], label: str
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > MAX_APPROVALS
        or any(not isinstance(item, str) or not pattern.fullmatch(item) for item in value)
        or value != sorted(set(value))
    ):
        raise MediaApprovalError(f"{label} must be a nonempty unique sorted list")
    return tuple(value)


def _strict_media_source_pages(value: object, *, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > MAX_APPROVALS
        or any(not isinstance(item, str) for item in value)
        or value != sorted(set(value))
    ):
        raise MediaApprovalError(f"{label} must be a nonempty unique sorted list")
    providers = {
        "usfws"
        if _USFWS_MEDIA_PAGE.fullmatch(item)
        else "inaturalist"
        if _INATURALIST_MEDIA_PAGE.fullmatch(item)
        else "invalid"
        for item in value
    }
    if "invalid" in providers or len(providers) != 1:
        raise MediaApprovalError(
            f"{label} must identify exact pages from one reviewed media provider"
        )
    return tuple(value)


def _valid_review_date(value: str) -> bool:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return date(2020, 1, 1) <= parsed <= date.today()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVAL_PATH)
    parser.add_argument("--write-review-candidates", type=Path)
    parser.add_argument("--import-local-decisions", type=Path)
    parser.add_argument("--write-updated-ledger", type=Path)
    parser.add_argument("--reviewed-by")
    parser.add_argument("--reviewed-at")
    parser.add_argument("--provider", choices=sorted(_MEDIA_PROVIDERS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    approval_path = args.approvals
    try:
        if args.import_local_decisions is not None:
            if args.write_updated_ledger is None or args.reviewed_by is None:
                raise MediaApprovalError("import requires --write-updated-ledger and --reviewed-by")
            imported = merge_local_review_decisions(
                args.manifest,
                args.approvals,
                args.import_local_decisions,
                args.write_updated_ledger,
                reviewed_by=args.reviewed_by,
                reviewed_at=args.reviewed_at,
            )
            print(json.dumps({"imported": asdict(imported)}, sort_keys=True))
            approval_path = args.write_updated_ledger
        elif args.write_updated_ledger is not None or args.reviewed_by is not None:
            raise MediaApprovalError("ledger output and reviewer require --import-local-decisions")
        if args.write_review_candidates is not None:
            count = write_review_candidates(
                args.manifest,
                approval_path,
                args.write_review_candidates,
            )
            print(f"Wrote {count} species/image media review candidate(s).")
        plan = require_visual_approvals(
            args.manifest,
            approval_path,
            provider=args.provider,
        )
    except (OSError, MediaApprovalError) as exc:
        print(f"Rufous media visual-selection gate failed: {exc}")
        return 1
    print(json.dumps(asdict(plan.summary), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
