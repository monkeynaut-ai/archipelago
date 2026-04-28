"""ChangeSetsDocument — Change Set Planner's output artifact.

A single document containing a list of `ChangeSetRef` items. Each item
is a `MarkdownHeader` with a name (rendered as the heading text) and a
free-prose summary section. The `slug` (used for filesystem paths
under `/workspace/documents/change-sets/{slug}/`) is derived from the
name via `slugify`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated

from archetype.markdown import AsHeading, MarkdownDocument, MarkdownHeader, TextTemplate
from pydantic import BaseModel, Field, computed_field, field_validator

_SLUG_UNSAFE = re.compile(r"[^a-zA-Z0-9-]+")


def slugify(text: str) -> str:
    """Lowercase, dash-separated, alphanumerics-only path slug.

    Empty input yields `unnamed` so callers always get a usable path
    component. Used by `ChangeSetRef.slug` and `StepRef.slug`.
    """
    cleaned = _SLUG_UNSAFE.sub("-", text.lower()).strip("-")
    return cleaned or "unnamed"


class ChangeSetRef(MarkdownHeader):
    title: Annotated[str, TextTemplate("{value}")] = Field(
        description="Human-readable name of this change set; renders as the heading."
    )

    summary: Annotated[str, AsHeading()] = Field(
        description=(
            "One-paragraph statement of what this change set delivers — "
            "why it stands alone as a shippable slice and what it changes."
        )
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        return slugify(self.title)


class ChangeSetsDocumentFrontmatter(BaseModel):
    feature_slug: str
    feature_name: str
    generated_at: str | date  # ISO timestamp; YAML may parse as date

    @field_validator("generated_at", mode="after")
    @classmethod
    def coerce_generated_at_to_string(cls, v):
        if isinstance(v, date):
            return v.isoformat()
        return v


class ChangeSetsDocument(MarkdownDocument):
    frontmatter: ChangeSetsDocumentFrontmatter | None = None
    title: Annotated[str, TextTemplate("Change sets for {value}")]
    change_sets: list[ChangeSetRef] = Field(
        description=(
            "Ordered list of change sets that, taken together, deliver the "
            "feature. Each is a self-contained shippable slice."
        )
    )
