"""Tests for the full_pipeline Loop `over` callables.

`_change_sets_over` and `_tasks_over` are the two projection functions
the outer and inner Loops use to compute the iterable they walk. The
contract is: read the typed document at the path stored in state, then
project the document field that holds the iteration items.

These tests pin both halves of that contract — the read goes through
`read_markdown` with the right path and document type, and the field
projection picks up the right list.
"""

from __future__ import annotations

from datetime import date

import pytest
from archetype.markdown import MarkdownHeader

from archipelago.actions import WorkspaceHandle
from archipelago.constants import (
    CHANGE_SETS_DIR_NAME,
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import (
    ChangeSetsDocument,
    Task,
    TDDPlan,
    TDDPlanFrontmatter,
)
from archipelago.systems.pipeline import (
    ChangeSetsLoopState,
    TDDPlanLoopState,
    _change_sets_over,
    _tasks_over,
)

from ..actions.test_workspace_io import _sample_change_sets_doc


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


@pytest.fixture
def fake_feature_definition(minimal_feature_definition):
    return minimal_feature_definition


def _change_sets_doc() -> ChangeSetsDocument:
    return _sample_change_sets_doc()


def _steps_doc() -> TDDPlan:
    return TDDPlan(
        frontmatter=TDDPlanFrontmatter(
            change_set_slug="slice-one",
            change_set_name="Slice One",
            generated_at=date(2026, 4, 30).isoformat(),
        ),
        title="Slice One",
        tasks=[
            Task(title="First Step", summary="Red.", task_details="d1"),
            Task(title="Second Step", summary="Green.", task_details="d2"),
        ],
    )


@pytest.fixture
def stub_read_markdown(monkeypatch):
    """Patch read_markdown at its imported location in pipeline.py and
    record the calls. The stub returns whatever the test installs in
    `stub.return_value`.

    `monkeypatch.setattr` raises AttributeError if `read_markdown` is
    not yet imported at this site — that's the red-phase signal that
    the projections still call into _ops directly.
    """
    calls: list[tuple[WorkspaceHandle, str, type[MarkdownHeader]]] = []

    class _Stub:
        return_value: object = None

        def __call__(
            self,
            workspace_handle: WorkspaceHandle,
            path: str,
            model_type: type[MarkdownHeader],
        ):
            calls.append((workspace_handle, path, model_type))
            return self.return_value

    stub = _Stub()
    monkeypatch.setattr("archipelago.systems.pipeline.read_markdown", stub)
    stub.calls = calls  # type: ignore[attr-defined]
    return stub


class TestChangeSetsOver:
    def test_given_state_when_called_then_read_markdown_called_with_handle_path_and_doc_type(
        self, stub_read_markdown, fake_feature_definition
    ):
        stub_read_markdown.return_value = _change_sets_doc()
        handle = _handle()
        state = ChangeSetsLoopState(
            change_sets_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
            workspace_handle=handle,
            design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
            feature_definition=fake_feature_definition,
        )

        _change_sets_over(state)

        assert stub_read_markdown.calls == [  # type: ignore[attr-defined]
            (handle, f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md", ChangeSetsDocument)
        ]

    def test_given_doc_when_called_then_returns_change_sets_field(
        self, stub_read_markdown, fake_feature_definition
    ):
        doc = _change_sets_doc()
        stub_read_markdown.return_value = doc
        state = ChangeSetsLoopState(
            change_sets_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}.md",
            workspace_handle=_handle(),
            design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
            feature_definition=fake_feature_definition,
        )

        result = _change_sets_over(state)

        assert result == doc.change_sets


class TestStepsOver:
    def test_given_state_when_called_then_read_markdown_called_with_handle_path_and_doc_type(
        self, stub_read_markdown
    ):
        stub_read_markdown.return_value = _steps_doc()
        handle = _handle()
        state = TDDPlanLoopState(
            tdd_plan_path=f"{WORKSPACE_DOCUMENTS_PATH}/change-sets/slice-one/tdd_plan.md",
            change_set_workspace_path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}/slice-one",
            workspace_handle=handle,
        )

        _tasks_over(state)

        assert stub_read_markdown.calls == [  # type: ignore[attr-defined]
            (
                handle,
                f"{WORKSPACE_DOCUMENTS_PATH}/change-sets/slice-one/tdd_plan.md",
                TDDPlan,
            )
        ]

    def test_given_doc_when_called_then_returns_steps_field(self, stub_read_markdown):
        doc = _steps_doc()
        stub_read_markdown.return_value = doc
        state = TDDPlanLoopState(
            tdd_plan_path=f"{WORKSPACE_DOCUMENTS_PATH}/change-sets/slice-one/tdd_plan.md",
            change_set_workspace_path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}/slice-one",
            workspace_handle=_handle(),
        )

        result = _tasks_over(state)

        assert result == doc.tasks
