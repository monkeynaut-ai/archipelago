"""CurrentTaskDocument — the per-iteration task-context artifact.

Embeds the active task in full plus a trimmed view of
its change set (purpose and acceptance criteria — the goal context, without
the full file list and change details that belong to the whole change set
rather than this one task). The frontmatter slugs give a re-invoked agent a
stable identity anchor for the change set and task it owns.
"""

from __future__ import annotations

from typing import Annotated

from archetype.markdown import AsHeading, MarkdownDocument, MarkdownHeader, TextTemplate
from pydantic import BaseModel

from archipelago.models.tdd_plan import Task


class ChangeSetContext(MarkdownHeader):
    title: Annotated[str, TextTemplate("{value}")]
    purpose: Annotated[str, AsHeading()]
    acceptance_criteria: Annotated[str, AsHeading()]


class CurrentTaskFrontmatter(BaseModel):
    change_set_slug: str
    task_slug: str
    tdd_plan_path: str


class CurrentTaskDocument(MarkdownDocument):
    frontmatter: CurrentTaskFrontmatter | None = None
    title: Annotated[str, TextTemplate("Current Task")] = "Current Task"

    change_set: ChangeSetContext
    task: Task
