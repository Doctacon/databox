"""Structured logging for databox sources.

One-shot `configure_logging()` wires structlog + stdlib logging with either
a human-friendly console renderer (local TTY) or a JSON renderer (CI,
production, any non-TTY). Every log line carries `timestamp`, `level`,
`event`, and any bound context keys.

Standard context keys (bind via `logger.bind(...)` or call kwargs):
  - pipeline:    dlt pipeline name (e.g. "ebird_api")
  - source:      source slug (e.g. "ebird")
  - resource:    dlt resource name (e.g. "recent_observations")
  - load_id:     dlt load_id when available
  - duration_ms: elapsed ms for the spanned work
  - rows:        row count produced/loaded

Maps to OpenTelemetry semantic conventions where practical so future OTel
export is mechanical.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(level: str | int | None = None) -> None:
    """Idempotently wire structlog + stdlib logging.

    Format selection:
      - DATABOX_LOG_FORMAT=json|console overrides
      - else: console if stderr is a TTY, else json
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_level = _resolve_level(level)
    fmt = os.getenv("DATABOX_LOG_FORMAT") or ("console" if sys.stderr.isatty() else "json")

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any
    if fmt == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through the same renderer so dlt / dagster logs
    # come out with the same shape.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved_level)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """Return a structlog BoundLogger. Call `configure_logging()` first."""
    configure_logging()
    return structlog.get_logger(name)


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        level = os.getenv("DATABOX_LOG_LEVEL", "INFO")
    if isinstance(level, int):
        return level
    return logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
