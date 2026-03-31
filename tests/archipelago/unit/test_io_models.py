"""Tests for per-agent output models and AgentWorkerResult."""

import pytest
from pydantic import ValidationError

from archipelago.agents.io_models import (
    CodeWriterOutput,
    DecomposerOutput,
    DispatcherOutput,
    EvaluatorOutput,
    SoftwareReviewerOutput,
    UnitTestWriterOutput,
)
from archipelago.models import AgentWorkerResult, CurrentTask

# ── AgentWorkerResult ──


class TestAgentWorkerResult:
    def test_given_valid_dict_when_validated_then_constructs(self):
        data = {
            "result_summary": "Code writer completed",
            "status": "completed",
            "output_lines": ["line1", "line2"],
        }
        result = AgentWorkerResult(**data)
        assert result.status == "completed"
        assert result.review is None

    def test_given_review_data_when_validated_then_includes_review(self):
        data = {
            "result_summary": "Software reviewer completed",
            "status": "completed",
            "output_lines": [],
            "review": {"summary": {"overall_rating": "good"}},
        }
        result = AgentWorkerResult(**data)
        assert result.review is not None
        assert result.review["summary"]["overall_rating"] == "good"

    def test_given_missing_status_when_validated_then_raises(self):
        with pytest.raises(ValidationError):
            AgentWorkerResult(result_summary="test")

    def test_given_invalid_status_when_validated_then_raises(self):
        with pytest.raises(ValidationError):
            AgentWorkerResult(result_summary="test", status="unknown")

    def test_given_valid_instance_when_dumped_then_roundtrips(self):
        result = AgentWorkerResult(
            result_summary="Code writer completed",
            status="completed",
            output_lines=["line1"],
        )
        dumped = result.model_dump()
        assert dumped == {
            "result_summary": "Code writer completed",
            "status": "completed",
            "output_lines": ["line1"],
            "review": None,
        }
        assert AgentWorkerResult(**dumped) == result


# ── Per-agent output models ──


def _worker_result(**overrides) -> AgentWorkerResult:
    defaults = {
        "result_summary": "Agent completed",
        "status": "completed",
        "output_lines": [],
    }
    return AgentWorkerResult(**(defaults | overrides))


class TestCodeWriterOutput:
    def test_given_valid_data_when_constructed_then_has_all_fields(self):
        output = CodeWriterOutput(
            worker_result=_worker_result(result_summary="Code writer completed"),
            workspace_volume="archipelago-123",
            commit_hash="abc789",
        )
        assert output.commit_hash == "abc789"
        assert output.workspace_volume == "archipelago-123"

    def test_given_instance_when_dumped_then_matches_current_state_shape(self):
        output = CodeWriterOutput(
            worker_result=_worker_result(),
            workspace_volume="archipelago-123",
            commit_hash="abc789",
        )
        dumped = output.model_dump()
        assert "worker_result" in dumped
        assert "workspace_volume" in dumped
        assert "commit_hash" in dumped
        assert dumped["worker_result"]["status"] == "completed"


class TestUnitTestWriterOutput:
    def test_given_valid_data_when_constructed_then_has_all_fields(self):
        output = UnitTestWriterOutput(
            worker_result=_worker_result(),
            workspace_volume="archipelago-123",
        )
        assert output.workspace_volume == "archipelago-123"

    def test_given_instance_when_dumped_then_matches_current_state_shape(self):
        output = UnitTestWriterOutput(
            worker_result=_worker_result(),
            workspace_volume="archipelago-123",
        )
        dumped = output.model_dump()
        assert set(dumped.keys()) == {"worker_result", "workspace_volume"}


class TestSoftwareReviewerOutput:
    def test_given_review_data_when_constructed_then_review_in_worker_result(self):
        output = SoftwareReviewerOutput(
            worker_result=_worker_result(review={"summary": {"overall_rating": "good"}}),
            workspace_volume="archipelago-123",
        )
        assert output.worker_result.review is not None

    def test_given_instance_when_dumped_then_matches_current_state_shape(self):
        output = SoftwareReviewerOutput(
            worker_result=_worker_result(),
            workspace_volume="archipelago-123",
        )
        dumped = output.model_dump()
        assert set(dumped.keys()) == {"worker_result", "workspace_volume"}


class TestEvaluatorOutput:
    def test_given_pass_when_constructed_then_commit_passed_true(self):
        output = EvaluatorOutput(commit_passed=True)
        assert output.commit_passed is True

    def test_given_instance_when_dumped_then_contains_commit_passed(self):
        output = EvaluatorOutput(commit_passed=False)
        dumped = output.model_dump()
        assert dumped == {"commit_passed": False}


class TestDecomposerOutput:
    def test_given_valid_data_when_constructed_then_has_all_fields(self):
        output = DecomposerOutput(
            objective="Build feature X",
            repo_url="https://github.com/org/repo",
            repo_ref="main",
            constraints=["no breaking changes"],
            commit_slices=[{"title": "Add tests"}],
            current_index=0,
        )
        assert output.objective == "Build feature X"
        assert len(output.commit_slices) == 1

    def test_given_instance_when_dumped_then_matches_current_state_shape(self):
        output = DecomposerOutput(
            objective="Build feature X",
            repo_url="https://github.com/org/repo",
            commit_slices=[{"title": "Add tests"}],
        )
        dumped = output.model_dump()
        expected_keys = {
            "objective",
            "repo_url",
            "repo_ref",
            "constraints",
            "commit_slices",
            "current_index",
        }
        assert set(dumped.keys()) == expected_keys


class TestDispatcherOutput:
    def test_given_valid_data_when_constructed_then_has_current_task(self):
        task = CurrentTask(objective="Build X", title="Add tests")
        output = DispatcherOutput(
            current_task=task,
            current_index=1,
            has_more_commits=True,
        )
        assert output.current_task.objective == "Build X"
        assert output.has_more_commits is True

    def test_given_instance_when_dumped_then_contains_current_task_dict(self):
        task = CurrentTask(objective="Build X", title="Add tests")
        output = DispatcherOutput(
            current_task=task,
            current_index=0,
            has_more_commits=False,
        )
        dumped = output.model_dump()
        assert "current_task" in dumped
        assert dumped["current_task"]["objective"] == "Build X"


# ── JSON Schema generation ──


class TestJsonSchemaGeneration:
    def test_given_agent_worker_result_when_schema_generated_then_valid(self):
        schema = AgentWorkerResult.model_json_schema()
        assert schema["type"] == "object"
        assert "result_summary" in schema["properties"]
        assert "status" in schema["properties"]

    def test_given_code_writer_output_when_schema_generated_then_references_worker_result(self):
        schema = CodeWriterOutput.model_json_schema()
        assert schema["type"] == "object"
        assert "worker_result" in schema["properties"]
        assert "commit_hash" in schema["properties"]

    def test_given_evaluator_output_when_schema_generated_then_minimal(self):
        schema = EvaluatorOutput.model_json_schema()
        assert schema["type"] == "object"
        assert "commit_passed" in schema["properties"]
