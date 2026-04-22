"""Parse the committed examples/features/run-observability.md and verify
it round-trips through FeatureDefinition cleanly.

The committed file uses sentence-case H2/H3 headings; archetype matches
case-insensitively (since agent-foundry dfb757f), so parsing succeeds.
"""

from __future__ import annotations

from pathlib import Path

from archetype.markdown import render_instance, validate_markdown

from archipelago.models.feature_definition import FeatureDefinition


class TestRunObservabilityParse:
    def test_given_committed_file_when_parsed_then_title_is_correct(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        fd = validate_markdown(text, FeatureDefinition)
        assert fd.title == "Run Observability"

    def test_given_committed_file_when_parsed_then_frontmatter_slug_is_correct(
        self, repo_root: Path
    ):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        fd = validate_markdown(text, FeatureDefinition)
        assert fd.frontmatter.feature_slug == "run-observability"

    def test_given_committed_file_when_parsed_then_body_sections_non_empty(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        fd = validate_markdown(text, FeatureDefinition)
        assert len(fd.problem_statement) > 50
        assert len(fd.feature_intent) > 50
        assert len(fd.desired_outcomes.user_outcomes.items) >= 3
        assert len(fd.desired_outcomes.business_outcomes.items) >= 3
        assert len(fd.scope_boundaries.items) >= 3
        assert len(fd.assumptions.items) >= 3
        assert len(fd.dependencies.items) >= 1
        assert len(fd.constraints.items) >= 1
        assert len(fd.acceptance_criteria.items) >= 5


class TestRunObservabilityRoundTrip:
    def test_given_committed_file_when_rendered_and_reparsed_then_semantically_equal(
        self, repo_root: Path
    ):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        fd = validate_markdown(text, FeatureDefinition)
        rendered = render_instance(fd)
        reparsed = validate_markdown(rendered, FeatureDefinition)
        assert reparsed == fd
