"""Stable public interface for explicit-target USFWS image metadata ingestion."""

from databox_sources.usfws.source import (
    USFWS_MAX_TARGET_SPECIES,
    UsfwsTarget,
    usfws_source,
)

__all__ = ["USFWS_MAX_TARGET_SPECIES", "UsfwsTarget", "usfws_source"]
