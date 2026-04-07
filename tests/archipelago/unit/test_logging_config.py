"""Tests for archipelago.logging_config.configure_logging."""

import logging

import pytest
import structlog

from archipelago.logging_config import configure_logging


@pytest.fixture(autouse=True)
def reset_root_logger():
    """Snapshot root logger state and restore it after each test.

    configure_logging clears and replaces handlers on the root logger, so we
    save/restore state to avoid test bleed.
    """
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = root.handlers[:]
    saved_websockets_level = logging.getLogger("websockets").level
    saved_urllib3_level = logging.getLogger("urllib3").level
    yield
    root.handlers.clear()
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)
    logging.getLogger("websockets").setLevel(saved_websockets_level)
    logging.getLogger("urllib3").setLevel(saved_urllib3_level)
    structlog.reset_defaults()


class TestLogLevel:
    def test_given_default_when_configured_then_root_is_info(self):
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_given_debug_when_configured_then_root_is_debug(self):
        configure_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_given_lowercase_when_configured_then_still_applied(self):
        configure_logging("warning")
        assert logging.getLogger().level == logging.WARNING

    def test_given_invalid_level_when_configured_then_falls_back_to_info(self):
        configure_logging("NONSENSE")
        assert logging.getLogger().level == logging.INFO


def _formatter_renderer(formatter: logging.Formatter) -> object | None:
    """Extract the terminal renderer from a structlog ProcessorFormatter.

    ProcessorFormatter.processors is a tuple whose last element is the
    terminal processor (the renderer) — the leading elements are
    helpers like remove_processors_meta.
    """
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    return formatter.processors[-1]


class TestFormatSelection:
    def test_given_log_format_json_when_configured_then_uses_json_renderer(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "json")
        configure_logging()
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        formatter = handlers[0].formatter
        assert formatter is not None
        renderer = _formatter_renderer(formatter)
        assert isinstance(renderer, structlog.processors.JSONRenderer)

    def test_given_log_format_unset_when_configured_then_uses_console_renderer(self, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_logging()
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        formatter = handlers[0].formatter
        assert formatter is not None
        renderer = _formatter_renderer(formatter)
        assert isinstance(renderer, structlog.dev.ConsoleRenderer)

    def test_given_log_format_non_json_when_configured_then_uses_console_renderer(
        self, monkeypatch
    ):
        monkeypatch.setenv("LOG_FORMAT", "pretty")
        configure_logging()
        handlers = logging.getLogger().handlers
        formatter = handlers[0].formatter
        assert formatter is not None
        renderer = _formatter_renderer(formatter)
        assert isinstance(renderer, structlog.dev.ConsoleRenderer)


class TestQuietedLoggers:
    def test_given_configured_when_checked_then_websockets_is_warning(self):
        configure_logging("DEBUG")
        assert logging.getLogger("websockets").level == logging.WARNING

    def test_given_configured_when_checked_then_urllib3_is_warning(self):
        configure_logging("DEBUG")
        assert logging.getLogger("urllib3").level == logging.WARNING


class TestIdempotency:
    def test_given_called_twice_when_checked_then_only_one_handler(self):
        configure_logging()
        configure_logging()
        assert len(logging.getLogger().handlers) == 1
