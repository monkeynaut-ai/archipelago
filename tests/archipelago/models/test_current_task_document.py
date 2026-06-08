"""Tests for CurrentTaskDocument."""

from __future__ import annotations

import pytest
from archetype.markdown import parse_markdown_as, render_markdown
from pydantic import ValidationError

from archipelago.models import (
    ChangeSetContext,
    CurrentTaskDocument,
    CurrentTaskFrontmatter,
    Task,
)


def _change_set() -> ChangeSetContext:
    return ChangeSetContext(
        heading="Persist verdict artifacts",
        purpose="Write per-attempt design-review verdicts.",
        acceptance_criteria="Each attempt produces a verdict file.",
    )


def _task() -> Task:
    return Task(
        heading="Write failing test for verdict writer",
        summary="Red step: assert a verdict file is written.",
        task_details="Add the test; run pytest; verify it fails.",
    )


def _document() -> CurrentTaskDocument:
    cs = _change_set()
    task = _task()
    return CurrentTaskDocument(
        frontmatter=CurrentTaskFrontmatter(
            change_set_slug="persist-verdict-artifacts",
            task_slug=task.slug,
            tdd_plan_path="/workspace/documents/change-sets/cs1/tdd-plan.md",
        ),
        change_set=cs,
        task=task,
    )


class TestCurrentTaskDocumentConstruction:
    def test_given_change_set_and_task_when_constructed_then_embedded(self):
        doc = _document()
        assert doc.change_set.heading == "Persist verdict artifacts"
        assert doc.task.heading == "Write failing test for verdict writer"

    def test_given_no_title_when_constructed_then_defaults_to_current_task(self):
        doc = _document()
        assert doc.heading == "Current Task"

    def test_given_missing_task_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            CurrentTaskDocument(change_set=_change_set())  # type: ignore[call-arg]


class TestCurrentTaskDocumentRender:
    def test_given_instance_when_rendered_then_h1_is_current_task(self):
        rendered = render_markdown(_document())
        assert "# Current Task" in rendered

    def test_given_instance_when_rendered_then_embedded_sections_present(self):
        rendered = render_markdown(_document())
        assert "## Persist verdict artifacts" in rendered
        assert "## Write failing test for verdict writer" in rendered
        assert "### Task Details" in rendered

    def test_given_instance_when_rendered_then_change_set_files_and_details_trimmed(self):
        rendered = render_markdown(_document())
        assert "### Files" not in rendered
        assert "### Details" not in rendered

    def test_given_instance_when_rendered_then_frontmatter_slugs_present(self):
        rendered = render_markdown(_document())
        for key in ["change_set_slug:", "task_slug:", "tdd_plan_path:"]:
            assert key in rendered, f"missing frontmatter key {key!r}"


class TestCurrentTaskDocumentRoundTrip:
    def test_given_instance_when_rendered_and_parsed_then_semantically_equal(self):
        doc = _document()
        reparsed = parse_markdown_as(render_markdown(doc), CurrentTaskDocument)
        assert reparsed == doc
