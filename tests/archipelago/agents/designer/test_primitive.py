"""Tests for the Designer AgentAction primitive config."""

from __future__ import annotations

from archipelago.agents.designer.primitive import designer
from archipelago.constants import GID_DOCUMENTS


class TestDesignerPrimitiveConfig:
    def test_given_designer_when_inspected_then_name_is_designer(self):
        assert designer.name == "designer"

    def test_given_designer_when_inspected_then_gids_are_documents_writer(self):
        assert designer.gids == [GID_DOCUMENTS]

    def test_given_designer_when_inspected_then_skip_permissions_is_true(self):
        assert designer.skip_permissions is True
