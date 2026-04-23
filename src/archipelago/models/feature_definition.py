"""FeatureDefinition — canonical Archipelago feature-spec document.

Nine top-level sections. Sections that render as H2 + bullet list are
declared as wrapper MarkdownHeader subclasses carrying a single
`items: list[str]` field, so list[str] typing survives the body-order
rule (every body field opens a heading).

Wrapper `title` defaults use Title Case so they align with
`archetype.markdown._shared.snake_to_title` output for top-level
heading-style fields. Parsing is case-insensitive (since archetype
commit dfb757f), so hand-authored feature defs may use either
sentence case or Title Case for H2/H3 headings.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from archetype.markdown import AsBulletList, AsHeading, MarkdownDocument, MarkdownHeader
from pydantic import BaseModel, Field, field_validator


class UserOutcomes(MarkdownHeader):
    title: str = "User Outcomes"
    items: Annotated[list[str], AsBulletList()]


class BusinessOutcomes(MarkdownHeader):
    title: str = "Business Outcomes"
    items: Annotated[list[str], AsBulletList()]


class DesiredOutcomes(MarkdownHeader):
    title: str = "Desired Outcomes"
    user_outcomes: UserOutcomes
    business_outcomes: BusinessOutcomes


class ScopeBoundaries(MarkdownHeader):
    title: str = "Scope Boundaries"
    items: Annotated[list[str], AsBulletList()]


class Assumptions(MarkdownHeader):
    title: str = "Assumptions"
    items: Annotated[list[str], AsBulletList()]


class Dependencies(MarkdownHeader):
    title: str = "Dependencies"
    items: Annotated[list[str], AsBulletList()]


class Constraints(MarkdownHeader):
    title: str = "Constraints"
    items: Annotated[list[str], AsBulletList()]


class AcceptanceCriteria(MarkdownHeader):
    title: str = "Acceptance Criteria"
    items: Annotated[list[str], AsBulletList()]


class FeatureDefinitionFrontmatter(BaseModel):
    feature_slug: str
    created_at: str | date  # ISO timestamp; string-typed on v1, but YAML may parse as date

    @field_validator("created_at", mode="after")
    @classmethod
    def coerce_created_at_to_string(cls, v):
        """YAML parser converts date strings to date objects; convert back to ISO string.

        This happens when YAML sees `created_at: 2026-04-20` (no quotes) and
        converts it to a Python date object. We need to convert it back to
        the ISO string format for storage.
        """
        if isinstance(v, date):
            return v.isoformat()
        return v


class FeatureDefinition(MarkdownDocument):
    frontmatter: FeatureDefinitionFrontmatter | None = None
    title: str = Field(description=("Feature name. Renders as the document's top-level heading."))

    problem_statement: Annotated[str, AsHeading()] = Field(
        description=(
            "The current pain or gap this feature addresses. What's "
            "broken or missing today, before this feature exists?"
        )
    )

    feature_intent: Annotated[str, AsHeading()] = Field(
        description=(
            "Why this feature is the chosen answer to the problem — what "
            "makes this the right solution versus other solutions to the "
            "same problem."
        )
    )

    desired_outcomes: DesiredOutcomes = Field(
        description=(
            "What good looks like after the feature ships, split into "
            "outcomes for users and outcomes for the business."
        )
    )

    scope_boundaries: ScopeBoundaries = Field(
        description=(
            "Explicit statements of what is out of scope — what this feature does NOT try to do."
        )
    )

    assumptions: Assumptions = Field(
        description=(
            "Truth-claims about the world the design will rest on — "
            "beliefs we're betting on without having verified."
        )
    )

    dependencies: Dependencies = Field(
        description=(
            "External things this feature relies on — services, prior "
            "changes, deployed infrastructure."
        )
    )

    constraints: Constraints = Field(
        description=(
            "Hard limits the solution must respect: must-do's, "
            "must-not-do's, non-functional requirements."
        )
    )

    acceptance_criteria: AcceptanceCriteria = Field(
        description=(
            "Concrete, testable statements of 'done' — what must be true "
            "when this feature is complete."
        )
    )
