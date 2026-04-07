"""Structlog configuration for the Archipelago pipeline.

Provides a single entry point, `configure_logging`, that wires up structlog
with JSON output in production (when `LOG_FORMAT=json`) and a readable
console renderer otherwise. Called once at process startup.

Extracted from the original `archipelago.cli` module during CS5 so the
logging setup survives the CLI rewrite in CS10.
"""

import logging
import os

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog with JSON output for production, readable output for development.

    Args:
        level: Log level name (INFO, DEBUG, WARNING, ERROR). Case-insensitive.
            Falls back to INFO if the value is not a valid stdlib logging level.

    Environment variables:
        LOG_FORMAT: Set to "json" (case-insensitive) to emit JSON log lines.
            Any other value (or unset) uses structlog's ConsoleRenderer.

    The handler list on the root logger is cleared before attaching a new
    handler — safe to call multiple times (e.g., tests). The `websockets`
    and `urllib3` loggers are silenced to WARNING to keep the pipeline
    output readable.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(),
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
