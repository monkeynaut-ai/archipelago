"""Tests for FeatureDefinition wrappers and document."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.models.feature_definition import (
    AcceptanceCriteria,
    Assumptions,
    BusinessOutcomes,
    Constraints,
    Dependencies,
    DesiredOutcomes,
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
