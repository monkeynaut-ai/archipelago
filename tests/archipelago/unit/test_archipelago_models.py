"""Archipelago artifact models — validation and round-trip tests."""

import pytest
from pydantic import ValidationError

from archipelago.models import (
    ChangeSet,
    CodeReview,
    CodeReviewFinding,
    CodeReviewScope,
    CodeReviewSummary,
    CurrentTask,
    JobSpecification,
    KernelState,
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


class TestChangeSet:
    def test_given_title_only_when_instantiated_then_defaults_applied(self):
        cs = ChangeSet(title="Add models")
        assert cs.title == "Add models"
        assert cs.acceptance_criteria == []
        assert cs.test_focus == ""
        assert cs.implementation_focus == ""

    def test_given_all_fields_when_json_round_tripped_then_no_field_loss(self):
        cs = ChangeSet(
            title="Add models",
            acceptance_criteria=["Model exists"],
            test_focus="unit tests",
            implementation_focus="Pydantic models",
        )
        reconstructed = ChangeSet.model_validate_json(cs.model_dump_json())
        assert reconstructed == cs


class TestJobSpecification:
    def test_given_valid_job_when_instantiated_then_change_sets_parsed(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            change_sets=[{"title": "Add models"}, {"title": "Add endpoints"}],
        )
        assert job.objective == "Add auth"
        assert job.repo_url == "https://github.com/org/repo"
        assert job.repo_ref == "main"
        assert len(job.change_sets) == 2
        assert job.constraints == []

    def test_given_missing_objective_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError):
            JobSpecification(repo_url="https://github.com/org/repo", change_sets=[{"title": "c1"}])

    def test_given_valid_job_when_json_round_tripped_then_no_field_loss(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            repo_ref="develop",
            constraints=["No new deps"],
            change_sets=[{"title": "Add models", "acceptance_criteria": ["Model exists"]}],
        )
        reconstructed = JobSpecification.model_validate_json(job.model_dump_json())
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


# ── CurrentTask ──


def _valid_current_task() -> dict:
    return {
        "objective": "Add user authentication",
        "repo_url": "https://github.com/org/repo",
        "repo_ref": "main",
        "constraints": ["no external dependencies"],
        "title": "Add login endpoint",
        "acceptance_criteria": ["POST /login returns JWT", "invalid credentials return 401"],
        "test_focus": "auth edge cases",
        "implementation_focus": "src/auth/login.py",
    }


class TestCurrentTask:
    def test_given_all_fields_when_current_task_created_then_all_fields_populated(self):
        task = CurrentTask(**_valid_current_task())
        assert task.objective == "Add user authentication"
        assert task.repo_url == "https://github.com/org/repo"
        assert task.repo_ref == "main"
        assert task.constraints == ["no external dependencies"]
        assert task.title == "Add login endpoint"
        assert len(task.acceptance_criteria) == 2
        assert task.test_focus == "auth edge cases"
        assert task.implementation_focus == "src/auth/login.py"

    def test_given_minimal_fields_when_current_task_created_then_defaults_applied(self):
        task = CurrentTask(objective="Add auth", title="Add login endpoint")
        assert task.repo_url is None
        assert task.repo_ref == "main"
        assert task.constraints == []
        assert task.acceptance_criteria == []
        assert task.test_focus == ""
        assert task.implementation_focus == ""

    def test_given_missing_objective_when_current_task_created_then_validation_error(self):
        with pytest.raises(ValidationError):
            CurrentTask(title="Add login endpoint")

    def test_given_dispatcher_output_when_current_task_constructed_then_round_trip_preserves_data(
        self,
    ):
        task = CurrentTask(**_valid_current_task())
        reconstructed = CurrentTask.model_validate_json(task.model_dump_json())
        assert reconstructed == task


# ── KernelState ──


class TestKernelState:
    def test_given_initial_entry_when_kernel_state_created_then_only_current_task_required(self):
        task = CurrentTask(**_valid_current_task())
        state = KernelState(current_task=task)
        assert state.current_task == task
        assert state.workspace_volume is None
        assert state.commit_hash is None
        assert state.worker_result is None
        assert state.commit_passed is None

    def test_given_full_state_when_kernel_state_created_then_all_fields_populated(self):
        task = CurrentTask(**_valid_current_task())
        state = KernelState(
            current_task=task,
            workspace_volume="archipelago-123",
            commit_hash="abc123",
            worker_result={"status": "completed"},
            commit_passed=True,
        )
        assert state.workspace_volume == "archipelago-123"
        assert state.commit_hash == "abc123"
        assert state.worker_result == {"status": "completed"}
        assert state.commit_passed is True

    def test_given_state_dict_when_kernel_state_constructed_then_round_trip_preserves_data(self):
        task = CurrentTask(**_valid_current_task())
        state = KernelState(
            current_task=task,
            workspace_volume="archipelago-123",
            commit_hash="abc123",
            commit_passed=True,
        )
        reconstructed = KernelState.model_validate_json(state.model_dump_json())
        assert reconstructed == state


# ── CodeReview ──


def _valid_finding() -> dict:
    return {
        "id": "F1",
        "quality": "cohesion",
        "severity": "major",
        "title": "Handler mixes lifecycle and task logic",
        "problem": "docker_worker_handler does input extraction, prompt building, and container management",
        "locations": [{"file": "src/archipelago/docker_worker/handler.py", "lines": "311-515"}],
        "suggestion": {"approach": "Split into lifecycle and role-specific classes"},
    }


def _valid_code_review() -> dict:
    return {
        "scope": {
            "paths": ["src/archipelago/docker_worker/handler.py"],
            "commit_range": "abc123..def456",
            "context": "Review of docker worker refactoring",
        },
        "summary": {
            "overall_rating": "needs_work",
            "strengths": ["Good test coverage"],
            "primary_concerns": ["Handler does too much"],
        },
        "findings": [_valid_finding()],
    }


class TestCodeReview:
    def test_given_complete_review_when_code_review_created_then_all_fields_populated(self):
        review = CodeReview(**_valid_code_review())
        assert review.scope.paths == ["src/archipelago/docker_worker/handler.py"]
        assert review.summary.overall_rating == "needs_work"
        assert len(review.findings) == 1
        assert review.findings[0].id == "F1"

    def test_given_minimal_review_when_code_review_created_then_defaults_applied(self):
        review = CodeReview(
            scope=CodeReviewScope(paths=["src/foo.py"]),
            summary=CodeReviewSummary(
                overall_rating="good",
                strengths=["Clean code"],
                primary_concerns=[],
            ),
            findings=[],
        )
        assert review.scope.commit_range is None
        assert review.scope.context is None
        assert review.findings == []

    def test_given_finding_when_created_then_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            CodeReviewFinding(
                id="F1",
                quality="cohesion",
                severity="major",
                # missing: title, problem, locations, suggestion
            )

    def test_given_invalid_severity_when_finding_created_then_validation_error(self):
        data = _valid_finding()
        data["severity"] = "extreme"
        with pytest.raises(ValidationError):
            CodeReviewFinding(**data)

    def test_given_invalid_quality_when_finding_created_then_validation_error(self):
        data = _valid_finding()
        data["quality"] = "prettiness"
        with pytest.raises(ValidationError):
            CodeReviewFinding(**data)
