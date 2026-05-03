"""Tester agent — runs the test suite for a single change set."""

from __future__ import annotations

from archipelago.agents.models import TesterInput, TesterOutput
from archipelago.agents.tester.primitive import tester

__all__ = [
    "TesterInput",
    "TesterOutput",
    "tester",
]
