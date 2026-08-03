"""Fail-closed metadata gate for marks restricted by official USFWS notices.

USFWS explicitly restricts reuse of its logo and applies the same restriction
to Federal and Junior Duck Stamp images, Federal Aid restoration symbols, and
the National Wildlife Refuge System's Blue Goose image:

https://www.fws.gov/notices
https://www.fws.gov/service/license-duck-stamps-or-junior-duck-stamp-imagery

This gate is deliberately metadata-only. It rejects records whose normalized
title, caption, alternative text, subject tags, or URLs identify a restricted
mark before Rufous downloads or publishes the associated bytes.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Iterable
from urllib.parse import unquote

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_MULTIPLE_SPACES = re.compile(r"\s+")

_LOGO_TERMS = frozenset({"logo", "logos", "logomark", "wordmark", "brandmark"})
_LOGO_PHRASES = ("brand mark", "logo mark", "word mark")
_MARK_TERMS = frozenset(
    {
        "emblem",
        "emblems",
        "insignia",
        "logo",
        "logos",
        "mark",
        "marks",
        "symbol",
        "symbols",
    }
)

_AGENCY_SEAL_PHRASES = (
    "agency seal",
    "department interior seal",
    "department of interior seal",
    "department of the interior seal",
    "doi seal",
    "fish and wildlife seal",
    "fish and wildlife service seal",
    "fish wildlife service seal",
    "fws seal",
    "official seal",
    "service seal",
    "us fish and wildlife seal",
    "us fish and wildlife service seal",
    "usfws seal",
)

_DUCK_STAMP_PHRASES = (
    "duck stamp",
    "duck stamps",
    "duckstamp",
    "duckstamps",
    "federal migratory bird hunting and conservation stamp",
    "migratory bird hunting and conservation stamp",
)

_FEDERAL_AID_PHRASES = (
    "federal aid in sport fish restoration",
    "federal aid in wildlife restoration",
    "federal aid sport fish restoration",
    "federal aid wildlife restoration",
)

_RESTORATION_PROGRAM_PHRASES = (
    "dingell johnson",
    "pittman robertson",
    "sport fish restoration",
    "wallop breaux",
    "wildlife and sport fish restoration",
    "wildlife restoration",
    "wildlife sport fish restoration",
    "wsfr",
)

_BLUE_GOOSE_PHRASES = (
    "blue goose refuge",
    "blue goose sign",
    "national wildlife refuge system blue goose",
    "national wildlife refuge system symbol",
    "refuge system blue goose",
)


def normalize_restricted_mark_text(value: str) -> str:
    """Return deterministic ASCII tokens for punctuation- and URL-safe matching."""
    decoded = html.unescape(value)
    # Official filenames occasionally percent-encode punctuation. Decode twice
    # so a doubly encoded separator cannot hide an otherwise explicit phrase.
    decoded = unquote(unquote(decoded))
    normalized = unicodedata.normalize("NFKD", decoded).encode("ascii", "ignore").decode()
    normalized = _NON_ALPHANUMERIC.sub(" ", normalized.casefold())
    return _MULTIPLE_SPACES.sub(" ", normalized).strip()


def restricted_usfws_mark_reason(values: Iterable[str | None]) -> str | None:
    """Classify restricted USFWS mark evidence, or return ``None`` when absent."""
    evidence = " ".join(
        normalized
        for value in values
        if isinstance(value, str) and (normalized := normalize_restricted_mark_text(value))
    )
    if not evidence:
        return None
    padded = f" {evidence} "
    tokens = set(evidence.split())

    if (
        tokens & _LOGO_TERMS
        or any(f" {phrase} " in padded for phrase in _LOGO_PHRASES)
        or any(f" {phrase} " in padded for phrase in _AGENCY_SEAL_PHRASES)
    ):
        return "service_or_agency_logo_or_seal"
    if any(f" {phrase} " in padded for phrase in _DUCK_STAMP_PHRASES):
        return "federal_or_junior_duck_stamp"
    if any(f" {phrase} " in padded for phrase in _FEDERAL_AID_PHRASES) or (
        bool(tokens & _MARK_TERMS)
        and any(f" {phrase} " in padded for phrase in _RESTORATION_PROGRAM_PHRASES)
    ):
        return "federal_aid_restoration_symbol"
    if any(f" {phrase} " in padded for phrase in _BLUE_GOOSE_PHRASES) or (
        " blue goose " in padded
        and (bool(tokens & _MARK_TERMS) or " national wildlife refuge system " in padded)
    ):
        return "blue_goose_refuge_mark"
    return None
