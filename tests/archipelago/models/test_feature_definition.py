"""Tests for FeatureDefinition wrappers and document."""

from __future__ import annotations

import pytest
from archetype.markdown import render_instance, template_fields, validate_markdown
from pydantic import ValidationError

from archipelago.models.feature_definition import (
    AcceptanceCriteria,
    Assumptions,
    BusinessOutcomes,
    Constraints,
    Dependencies,
    DesiredOutcomes,
    FeatureDefinition,
    FeatureDefinitionFrontmatter,
    ScopeBoundaries,
    UserOutcomes,
)


class TestWrapperDefaults:
    """Every wrapper has a default title matching snake_to_title's output
    for the corresponding top-level field name."""

    def test_given_user_outcomes_when_default_constructed_then_title_is_user_outcomes(self):
        assert UserOutcomes(items=["x"]).title == "User Outcomes"

    def test_given_business_outcomes_when_default_constructed_then_title_is_business_outcomes(self):
        assert BusinessOutcomes(items=["x"]).title == "Business Outcomes"

    def test_given_scope_boundaries_when_default_constructed_then_title_is_scope_boundaries(self):
        assert ScopeBoundaries(items=["x"]).title == "Scope Boundaries"

    def test_given_assumptions_when_default_constructed_then_title_is_assumptions(self):
        assert Assumptions(items=["x"]).title == "Assumptions"

    def test_given_dependencies_when_default_constructed_then_title_is_dependencies(self):
        assert Dependencies(items=["x"]).title == "Dependencies"

    def test_given_constraints_when_default_constructed_then_title_is_constraints(self):
        assert Constraints(items=["x"]).title == "Constraints"

    def test_given_acceptance_criteria_when_default_constructed_then_title_is_acceptance_criteria(
        self,
    ):
        assert AcceptanceCriteria(items=["x"]).title == "Acceptance Criteria"

    def test_given_desired_outcomes_when_default_constructed_then_title_is_desired_outcomes(self):
        wrapper = DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u"]),
            business_outcomes=BusinessOutcomes(items=["b"]),
        )
        assert wrapper.title == "Desired Outcomes"


class TestSimpleWrapperContent:
    def test_given_empty_items_when_constructed_then_items_is_empty_list(self):
        assert UserOutcomes(items=[]).items == []

    def test_given_list_of_strings_when_constructed_then_items_preserved(self):
        wrapper = ScopeBoundaries(items=["no dashboard", "no visualization"])
        assert wrapper.items == ["no dashboard", "no visualization"]

    def test_given_non_string_item_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            Assumptions(items=[123])  # type: ignore[list-item]


class TestDesiredOutcomesNesting:
    def test_given_nested_wrappers_when_constructed_then_instances_preserved(self):
        wrapper = DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u1", "u2"]),
            business_outcomes=BusinessOutcomes(items=["b1"]),
        )
        assert wrapper.user_outcomes.items == ["u1", "u2"]
        assert wrapper.business_outcomes.items == ["b1"]


class TestFeatureDefinitionFrontmatter:
    def test_given_slug_and_timestamp_when_constructed_then_fields_populated(self):
        fm = FeatureDefinitionFrontmatter(feature_slug="demo", created_at="2026-04-21")
        assert fm.feature_slug == "demo"
        assert fm.created_at == "2026-04-21"

    def test_given_missing_slug_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            FeatureDefinitionFrontmatter(created_at="2026-04-21")  # type: ignore[call-arg]


class TestFeatureDefinitionConstruction:
    def test_given_all_sections_when_constructed_then_no_error(self, minimal_feature_definition):
        fd = minimal_feature_definition
        assert fd.title == "Demo Feature"
        assert fd.problem_statement == "A gap exists."
        assert fd.assumptions.items == ["a1"]

    def test_given_missing_problem_statement_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            FeatureDefinition(
                frontmatter=FeatureDefinitionFrontmatter(feature_slug="x", created_at="x"),
                title="x",
                feature_intent="x",
                desired_outcomes=DesiredOutcomes(
                    user_outcomes=UserOutcomes(items=[]),
                    business_outcomes=BusinessOutcomes(items=[]),
                ),
                scope_boundaries=ScopeBoundaries(items=[]),
                assumptions=Assumptions(items=[]),
                dependencies=Dependencies(items=[]),
                constraints=Constraints(items=[]),
                acceptance_criteria=AcceptanceCriteria(items=[]),
            )  # type: ignore[call-arg]


class TestFeatureDefinitionTemplateFields:
    def test_given_feature_definition_when_template_fields_then_eight_entries(self):
        fields = template_fields(FeatureDefinition)
        assert len(fields) == 8

    def test_given_feature_definition_when_template_fields_then_headings_match(self):
        fields = template_fields(FeatureDefinition)
        assert [f.heading for f in fields] == [
            "Problem Statement",
            "Feature Intent",
            "Desired Outcomes",
            "Scope Boundaries",
            "Assumptions",
            "Dependencies",
            "Constraints",
            "Acceptance Criteria",
        ]

    def test_given_feature_definition_when_template_fields_then_every_field_has_description(self):
        fields = template_fields(FeatureDefinition)
        for field in fields:
            assert field.description is not None, f"{field.heading} has no description"
            assert len(field.description) > 20, f"{field.heading} description too short"


class TestFeatureDefinitionRoundTrip:
    def test_given_instance_when_rendered_then_h1_present(self, minimal_feature_definition):
        rendered = render_instance(minimal_feature_definition)
        assert "# Demo Feature" in rendered

    def test_given_instance_when_rendered_then_all_h2_sections_present(
        self, minimal_feature_definition
    ):
        rendered = render_instance(minimal_feature_definition)
        for heading in [
            "## Problem Statement",
            "## Feature Intent",
            "## Desired Outcomes",
            "## Scope Boundaries",
            "## Assumptions",
            "## Dependencies",
            "## Constraints",
            "## Acceptance Criteria",
        ]:
            assert heading in rendered, f"missing {heading!r}"

    def test_given_instance_when_rendered_and_parsed_then_semantically_equal(
        self, minimal_feature_definition
    ):
        rendered = render_instance(minimal_feature_definition)
        reparsed = validate_markdown(rendered, FeatureDefinition)
        assert reparsed == minimal_feature_definition
