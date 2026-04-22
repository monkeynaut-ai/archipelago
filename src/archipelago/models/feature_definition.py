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

from typing import Annotated

from archetype.markdown import AsBulletList, MarkdownHeader


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
