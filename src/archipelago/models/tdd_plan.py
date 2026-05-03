"""TDDPlan — TDD Planner's output artifact.

A single document, one per change set, containing a list of `Task`
items. Each item is a `MarkdownHeader` with a name and a summary; slug
is derived from the name.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from archetype.markdown import AsHeading, MarkdownDocument, MarkdownHeader, TextTemplate
from pydantic import BaseModel, Field, computed_field, field_validator

from archipelago.models.change_sets_document import slugify


class Task(MarkdownHeader):
    """
    Title
    Files
    Dependencies (e.g. other tasks)
    Spec for failing tests
        (instructions - run tests and verify they fail)
    Spec for implementation
        (instructions - continue implementation until all tests pass)
    (instructions - commit)
    """

    title: Annotated[str, TextTemplate("{value}")] = Field(
        description="Human-readable name of this task; renders as the heading."
    )

    summary: Annotated[str, AsHeading()] = Field(
        description=(
            "One-paragraph description of what this task does — a coherent "
            "red-green-refactor unit within the change set."
        )
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        return slugify(self.title)


class TDDPlanFrontmatter(BaseModel):
    change_set_slug: str
    change_set_name: str
    generated_at: str | date

    @field_validator("generated_at", mode="after")
    @classmethod
    def coerce_generated_at_to_string(cls, v):
        if isinstance(v, date):
            return v.isoformat()
        return v


class TDDPlan(MarkdownDocument):
    frontmatter: TDDPlanFrontmatter | None = None
    title: Annotated[str, TextTemplate("TDD Plan for change set {value}")]
    tasks: list[Task] = Field(
        description=(
            "Ordered list of TDD tasks within this change set. Each task is "
            "a coherent red-green-refactor unit."
        )
    )
