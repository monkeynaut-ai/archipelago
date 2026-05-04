"""Tests for the workspace_io.read_markdown helper.

read_markdown wraps "spawn an alpine container, cat the file, validate
against the model type" so Loop projections (and other callers that
read shared markdown documents from the workspace volume) can stay
small and don't have to import workspace_ops or docker directly.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from archetype.markdown import MarkdownValidationError, render_instance

from archipelago.actions import WorkspaceHandle, workspace_io
from archipelago.constants import (
    CHANGE_SETS_DIR_NAME,
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import (
    ChangeSetRef,
    ChangeSetsDocument,
    ChangeSetsDocumentFrontmatter,
)


def _handle(volume_name: str = "ws") -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name=volume_name,
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


def _sample_change_sets_doc() -> ChangeSetsDocument:
    return ChangeSetsDocument(
        frontmatter=ChangeSetsDocumentFrontmatter(
            feature_slug="demo",
            feature_name="Demo Feature",
            generated_at=date(2026, 4, 30).isoformat(),
        ),
        title="Demo Feature",
        tech_stack="marshall amps",
        change_sets=[
            ChangeSetRef(
                title="First Slice",
                purpose="Stand it up.",
                details="wow, more!",
                files="files",
                acceptance_criteria="great finale",
            ),
            ChangeSetRef(
                title="Second Slice",
                purpose="Wire it together.",
                details="on and on",
                files="files",
                acceptance_criteria="fine bouquet",
            ),
        ],
    )


@pytest.fixture
def patched_io():
    """Patch docker.from_env and workspace_ops.read_file to keep tests
    hermetic. Yields the (read_file mock, from_env mock) pair so each
    test can configure read_file's return value or side_effect."""
    with (
        patch("archipelago.actions.workspace_io.docker.from_env") as from_env,
        patch("archipelago.actions.workspace_io.workspace_ops.read_file") as read_file,
    ):
        client = MagicMock(name="docker_client")
        from_env.return_value = client
        yield read_file, from_env, client


class TestReadMarkdown:
    def test_given_handle_when_called_then_read_file_called_with_volume_and_path(self, patched_io):
        read_file, _, client = patched_io
        read_file.return_value = render_instance(_sample_change_sets_doc())

        workspace_io.read_markdown(
            _handle("my-vol"),
            f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
            ChangeSetsDocument,
        )

        read_file.assert_called_once_with(
            client,
            volume_name="my-vol",
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
        )

    def test_given_valid_markdown_when_called_then_returns_validated_instance(self, patched_io):
        read_file, _, _ = patched_io
        expected = _sample_change_sets_doc()
        read_file.return_value = render_instance(expected)

        result = workspace_io.read_markdown(
            _handle(),
            f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
            ChangeSetsDocument,
        )

        assert isinstance(result, ChangeSetsDocument)
        assert result == expected

    def test_given_invalid_markdown_when_called_then_validation_error_propagates(self, patched_io):
        read_file, _, _ = patched_io
        read_file.return_value = "not a valid change-sets document"

        with pytest.raises(MarkdownValidationError):
            workspace_io.read_markdown(
                _handle(),
                f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
                ChangeSetsDocument,
            )

    def test_given_read_file_error_when_called_then_runtime_error_propagates(self, patched_io):
        read_file, _, _ = patched_io
        read_file.side_effect = RuntimeError("read_file boom")

        with pytest.raises(RuntimeError, match="read_file boom"):
            workspace_io.read_markdown(
                _handle(),
                f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
                ChangeSetsDocument,
            )

    def test_given_call_when_invoked_then_docker_from_env_called_once(self, patched_io):
        read_file, from_env, _ = patched_io
        read_file.return_value = render_instance(_sample_change_sets_doc())

        workspace_io.read_markdown(
            _handle(),
            f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
            ChangeSetsDocument,
        )

        from_env.assert_called_once_with()
