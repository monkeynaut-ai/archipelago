"""Archipelago artifact models — validation and round-trip tests."""

import pytest
from pydantic import ValidationError

from archipelago.models import (
    CodePatch,
    TestResults,
)


def _valid_code_patch() -> dict:
    return {
        "feature_name": "Pipeline Orchestrator",
        "files_changed": ["src/archipelago/handlers.py", "src/archipelago/runner.py"],
        "diff_summary": "Added strategy and architecture handlers",
        "branch_name": "feat/archipelago-handlers",
    }


def _valid_test_results() -> dict:
    return {
        "feature_name": "Pipeline Orchestrator",
        "tests_passed": 12,
        "tests_failed": 0,
        "test_output": "12 passed in 0.5s",
        "all_green": True,
    }


class TestCodePatch:
    def test_given_valid_fields_when_instantiated_then_validates(self):
        patch = CodePatch(**_valid_code_patch())
        assert patch.feature_name == "Pipeline Orchestrator"
        assert len(patch.files_changed) == 2
        assert patch.branch_name == "feat/archipelago-handlers"

    def test_given_valid_instance_when_json_round_tripped_then_no_field_loss(self):
        patch = CodePatch(**_valid_code_patch())
        json_str = patch.model_dump_json()
        reconstructed = CodePatch.model_validate_json(json_str)
        assert reconstructed == patch


class TestTestResults:
    def test_given_valid_fields_when_instantiated_then_validates(self):
        results = TestResults(**_valid_test_results())
        assert results.tests_passed == 12
        assert results.tests_failed == 0
        assert results.all_green is True

    def test_given_valid_instance_when_json_round_tripped_then_no_field_loss(self):
        results = TestResults(**_valid_test_results())
        json_str = results.model_dump_json()
        reconstructed = TestResults.model_validate_json(json_str)
        assert reconstructed == results

    def test_given_missing_required_field_when_instantiated_then_raises_validation_error(self):
        data = _valid_test_results()
        del data["all_green"]
        with pytest.raises(ValidationError) as exc_info:
            TestResults(**data)
        field_names = [e["loc"][0] for e in exc_info.value.errors()]
        assert "all_green" in field_names
