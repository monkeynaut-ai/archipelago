"""Archipelago artifact models — validation and round-trip tests."""

import pytest
from pydantic import ValidationError

from archipelago.models import (
    CommitSpecification,
    JobDefinition,
    TestResults,
)


def _valid_test_results() -> dict:
    return {
        "feature_name": "Pipeline Orchestrator",
        "tests_passed": 12,
        "tests_failed": 0,
        "test_output": "12 passed in 0.5s",
        "all_green": True,
    }


class TestCommitSpecification:
    def test_given_title_only_when_instantiated_then_defaults_applied(self):
        cs = CommitSpecification(title="Add models")
        assert cs.title == "Add models"
        assert cs.acceptance_criteria == []
        assert cs.test_focus == ""
        assert cs.implementation_focus == ""

    def test_given_all_fields_when_json_round_tripped_then_no_field_loss(self):
        cs = CommitSpecification(
            title="Add models",
            acceptance_criteria=["Model exists"],
            test_focus="unit tests",
            implementation_focus="Pydantic models",
        )
        reconstructed = CommitSpecification.model_validate_json(cs.model_dump_json())
        assert reconstructed == cs


class TestJobDefinition:
    def test_given_valid_job_when_instantiated_then_commits_parsed(self):
        job = JobDefinition(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            commits=[{"title": "Add models"}, {"title": "Add endpoints"}],
        )
        assert job.objective == "Add auth"
        assert job.repo_url == "https://github.com/org/repo"
        assert job.repo_ref == "main"
        assert len(job.commits) == 2
        assert job.constraints == []

    def test_given_empty_commits_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError, match="commits must not be empty"):
            JobDefinition(objective="Add auth", repo_url="https://github.com/org/repo", commits=[])

    def test_given_missing_objective_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError):
            JobDefinition(repo_url="https://github.com/org/repo", commits=[{"title": "c1"}])

    def test_given_valid_job_when_json_round_tripped_then_no_field_loss(self):
        job = JobDefinition(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            repo_ref="develop",
            constraints=["No new deps"],
            commits=[{"title": "Add models", "acceptance_criteria": ["Model exists"]}],
        )
        reconstructed = JobDefinition.model_validate_json(job.model_dump_json())
        assert reconstructed == job


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
