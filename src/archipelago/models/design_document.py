"""DesignDocument — the Designer agent's output artifact.

Eight sections, all `Annotated[str, AsHeading()]` — free markdown prose
per section. H1 line uses `TextTemplate("Design for {value}")` to
disambiguate from the FeatureDefinition's H1.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from archetype.markdown import AsHeading, MarkdownDocument, TextTemplate
from pydantic import BaseModel, Field, field_validator


class DesignDocumentFrontmatter(BaseModel):
    feature_slug: str
    feature_name: str
    feature_definition_path: str
    codebase_ref: str
    codebase_resolved_sha: str
    generated_at: str | date  # ISO timestamp; string-typed on v1, but YAML may parse as date

    @field_validator("generated_at", mode="after")
    @classmethod
    def coerce_generated_at_to_string(cls, v):
        """YAML parser converts date/datetime strings to objects; convert back to ISO string.

        This handles both date and datetime objects that YAML's parser may create
        when it sees unquoted date-like values.
        """
        if isinstance(v, date):
            # If it's a date (not datetime), convert to ISO string
            return v.isoformat()
        # If it's already a string, return as-is
        return v


class DesignDocument(MarkdownDocument):
    frontmatter: DesignDocumentFrontmatter | None = None
    heading: Annotated[str, TextTemplate("Design for {value}")]

    summary: Annotated[str, AsHeading()] = Field(
        description="A one-paragraph framing of the proposed design."
    )

    current_state_context: Annotated[str, AsHeading()] = Field(
        description=(
            "Relevant existing codebase state found during investigation. "
            "Include only what's load-bearing for understanding the proposal. "
            "Do not summarize the entire codebase."
        )
    )

    components: Annotated[str, AsHeading()] = Field(
        description=(
            "The components — new or modified — that make up the design. "
            "Name each one, state its purpose, and what concern it owns."
        )
    )

    architecture: Annotated[str, AsHeading()] = Field(
        description=(
            "How the components interact: interfaces between them, control "
            "flow (orchestration and sequencing), and data flow (what moves, "
            "in what shape, from where to where)."
        )
    )

    acceptance_criteria: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level acceptance criteria refined from the feature "
            "definition. Concrete, testable statements of what must be "
            "true when the feature is complete."
        )
    )

    test_strategy: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level test approach: what to test, at what level "
            "(unit, integration, end-to-end), what fixtures or harnesses "
            "are needed."
        )
    )

    risks_and_open_items: Annotated[str, AsHeading()] = Field(
        description=(
            "Concerns and uncertainties the design leaves open: bets made, "
            "decisions deferred, areas where later stages will need judgment."
        )
    )

    resolved_assumptions: Annotated[str, AsHeading()] = Field(
        description=(
            "Disposition of each assumption in the feature definition — "
            "accepted, refined, promoted to constraint, or contradicted — "
            "plus any new assumptions introduced during design."
        )
    )
