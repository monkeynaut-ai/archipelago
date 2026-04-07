"""Archipelago artifact models — validation and round-trip tests."""

import pytest
from pydantic import ValidationError

from archipelago.models import (
    ChangeSet,
    ChangeSetStep,
    CodeReview,
    CodeReviewFinding,
    CodeReviewScope,
    CodeReviewSummary,
    CurrentTask,
    DispatchedFinding,
    DispatcherOutput,
    Disposition,
    FindingOrigin,
    ImplementationTask,
    IntegratorOutput,
    JobSpecification,
    OriginKind,
    ReviewFinding,
    Severity,
    StepOrigin,
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
    def test_given_name_and_intent_when_instantiated_then_defaults_applied(self):
        cs = ChangeSet(name="Add models", intent="install types")
        assert cs.name == "Add models"
        assert cs.intent == "install types"
        assert cs.acceptance_criteria == []
        assert cs.interface_specifications is None
        assert cs.steps == []

    def test_given_all_fields_when_json_round_tripped_then_no_field_loss(self):
        cs = ChangeSet(
            name="Add models",
            intent="install Pydantic types for job artifacts",
            acceptance_criteria=["Model exists"],
            interface_specifications=["class ChangeSet(BaseModel): ..."],
            steps=[],
        )
        reconstructed = ChangeSet.model_validate_json(cs.model_dump_json())
        assert reconstructed == cs

    def test_given_missing_name_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ChangeSet(intent="install types")  # type: ignore[call-arg]

    def test_given_missing_intent_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ChangeSet(name="Add models")  # type: ignore[call-arg]


class TestJobSpecification:
    def test_given_valid_job_when_instantiated_then_change_sets_parsed(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            change_sets=[
                {"name": "Add models", "intent": "install types"},
                {"name": "Add endpoints", "intent": "wire up routes"},
            ],
        )
        assert job.objective == "Add auth"
        assert job.repo_url == "https://github.com/org/repo"
        assert job.repo_ref == "main"
        assert len(job.change_sets) == 2
        assert job.constraints == []
        assert job.test_paths == []

    def test_given_missing_objective_when_instantiated_then_raises_validation_error(self):
        with pytest.raises(ValidationError):
            JobSpecification(
                repo_url="https://github.com/org/repo",
                change_sets=[{"name": "c1", "intent": "i1"}],
            )

    def test_given_explicit_test_paths_when_instantiated_then_stored(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            change_sets=[{"name": "c1", "intent": "i1"}],
            test_paths=["tests/unit", "tests/integration"],
        )
        assert job.test_paths == ["tests/unit", "tests/integration"]

    def test_given_valid_job_when_json_round_tripped_then_no_field_loss(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            repo_ref="develop",
            constraints=["No new deps"],
            test_paths=["tests/unit"],
            change_sets=[
                {
                    "name": "Add models",
                    "intent": "install types",
                    "acceptance_criteria": ["Model exists"],
                }
            ],
        )
        reconstructed = JobSpecification.model_validate_json(job.model_dump_json())
        assert reconstructed == job


class TestChangeSetStep:
    def test_given_description_only_when_instantiated_then_defaults_applied(self):
        step = ChangeSetStep(description="Add the ReviewFinding model")
        assert step.description == "Add the ReviewFinding model"
        assert step.acceptance_criteria_addressed == []

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        step = ChangeSetStep(
            description="Add the ReviewFinding model",
            acceptance_criteria_addressed=["New models exist", "Tests pass"],
        )
        assert ChangeSetStep.model_validate_json(step.model_dump_json()) == step


class TestReviewFinding:
    def test_given_enum_severity_when_instantiated_then_fields_stored(self):
        finding = ReviewFinding(
            description="Function name is ambiguous",
            severity=Severity.CAN_DEFER,
            category="naming",
        )
        assert finding.severity is Severity.CAN_DEFER
        assert finding.category == "naming"
        assert finding.affected_files_and_locations == []
        assert finding.suggested_resolution == ""
        assert finding.source_commit_hashes == []

    def test_given_string_severity_when_instantiated_then_coerced_to_enum(self):
        # Agent output arrives as JSON strings — Pydantic must coerce.
        finding = ReviewFinding(
            description="Function returns wrong type",
            severity="must_fix",
            category="code_quality",
        )
        assert finding.severity is Severity.MUST_FIX

    def test_given_invalid_severity_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                description="x",
                severity="critical",  # not a Severity member
                category="code_quality",
            )

    def test_given_nonstandard_category_when_instantiated_then_accepted(self):
        # category is a free str — the Reviewer can invent labels if needed
        finding = ReviewFinding(
            description="x",
            severity=Severity.CAN_DEFER,
            category="accessibility",
        )
        assert finding.category == "accessibility"

    def test_given_severity_when_dumped_to_json_then_serializes_as_string(self):
        finding = ReviewFinding(
            description="x",
            severity=Severity.MUST_FIX,
            category="code_quality",
        )
        dumped = finding.model_dump_json()
        assert '"severity":"must_fix"' in dumped

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        finding = ReviewFinding(
            description="Function name is ambiguous",
            severity=Severity.CAN_DEFER,
            category="naming",
            affected_files_and_locations=["src/foo.py:42"],
            suggested_resolution="Rename `process` to `compile_primitive`",
            source_commit_hashes=["abc123"],
        )
        assert ReviewFinding.model_validate_json(finding.model_dump_json()) == finding


class TestImplementationTask:
    def test_given_step_origin_when_instantiated_then_origin_is_step(self):
        task = ImplementationTask(
            origin=StepOrigin(step=ChangeSetStep(description="Add models")),
            implementation_change="Add pydantic classes to models.py",
        )
        assert task.origin.kind is OriginKind.STEP
        assert task.origin.step.description == "Add models"

    def test_given_finding_origin_when_instantiated_then_origin_is_finding(self):
        finding = ReviewFinding(
            description="Ambiguous name",
            severity=Severity.MUST_FIX,
            category="naming",
        )
        task = ImplementationTask(
            origin=FindingOrigin(finding=finding),
            implementation_change="Rename `process` to `compile_primitive`",
        )
        assert task.origin.kind is OriginKind.FINDING
        assert task.origin.finding.severity is Severity.MUST_FIX

    def test_given_dict_with_kind_step_when_parsed_then_discriminated_to_step(self):
        data = {
            "origin": {"kind": "step", "step": {"description": "Add models"}},
            "implementation_change": "Add pydantic classes",
        }
        task = ImplementationTask.model_validate(data)
        assert isinstance(task.origin, StepOrigin)

    def test_given_dict_with_kind_finding_when_parsed_then_discriminated_to_finding(self):
        data = {
            "origin": {
                "kind": "finding",
                "finding": {
                    "description": "x",
                    "severity": "must_fix",
                    "category": "naming",
                },
            },
            "implementation_change": "y",
        }
        task = ImplementationTask.model_validate(data)
        assert isinstance(task.origin, FindingOrigin)

    def test_given_missing_kind_discriminator_when_parsed_then_validation_error(self):
        data = {
            "origin": {"step": {"description": "Add models"}},  # no kind
            "implementation_change": "x",
        }
        with pytest.raises(ValidationError):
            ImplementationTask.model_validate(data)

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        task = ImplementationTask(
            origin=StepOrigin(
                step=ChangeSetStep(
                    description="Add models",
                    acceptance_criteria_addressed=["Models exist"],
                )
            ),
            interface_specifications=["ReviewFinding(BaseModel)"],
            unit_test_changes=["add: construction sets defaults"],
            implementation_change="Create pydantic classes",
        )
        assert ImplementationTask.model_validate_json(task.model_dump_json()) == task


class TestChangeSetStepsTightening:
    def test_given_change_set_with_steps_when_instantiated_then_steps_typed(self):
        step = ChangeSetStep(description="Add models")
        cs = ChangeSet(name="CS5", intent="data models", steps=[step])
        assert isinstance(cs.steps[0], ChangeSetStep)

    def test_given_change_set_with_dict_step_when_instantiated_then_coerced(self):
        cs = ChangeSet(
            name="CS5",
            intent="data models",
            steps=[{"description": "Add models"}],
        )
        assert isinstance(cs.steps[0], ChangeSetStep)
        assert cs.steps[0].description == "Add models"


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


class TestDispatchedFinding:
    def test_given_route_disposition_when_instantiated_then_target_stored(self):
        df = DispatchedFinding(
            finding=ReviewFinding(
                description="x",
                severity=Severity.CAN_DEFER,
                category="code_quality",
            ),
            disposition=Disposition.ROUTE_TO_CHANGE_SET,
            target_change_set_name="Cleanup Pass",
            rationale="Touches the same subsystem",
        )
        assert df.disposition is Disposition.ROUTE_TO_CHANGE_SET
        assert df.target_change_set_name == "Cleanup Pass"

    def test_given_string_disposition_when_instantiated_then_coerced_to_enum(self):
        df = DispatchedFinding(
            finding=ReviewFinding(
                description="x",
                severity=Severity.CAN_DEFER,
                category="code_quality",
            ),
            disposition="defer_to_post_job",
            rationale="Out of scope",
        )
        assert df.disposition is Disposition.DEFER_TO_POST_JOB
        assert df.target_change_set_name is None

    def test_given_invalid_disposition_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            DispatchedFinding(
                finding=ReviewFinding(
                    description="x",
                    severity=Severity.CAN_DEFER,
                    category="code_quality",
                ),
                disposition="ignore",
                rationale="nope",
            )


class TestDispatcherOutput:
    def test_given_empty_when_instantiated_then_all_lists_empty(self):
        out = DispatcherOutput()
        assert out.routed_findings == []
        assert out.deferred_findings == []
        assert out.escalations == []

    def test_given_mixed_dispositions_when_round_tripped_then_no_field_loss(self):
        finding = ReviewFinding(
            description="x",
            severity=Severity.CAN_DEFER,
            category="code_quality",
        )
        out = DispatcherOutput(
            routed_findings=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.ROUTE_TO_CHANGE_SET,
                    target_change_set_name="CS7",
                    rationale="fits",
                )
            ],
            deferred_findings=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.DEFER_TO_POST_JOB,
                    rationale="out of scope",
                )
            ],
            escalations=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.ESCALATE,
                    rationale="ambiguous",
                )
            ],
        )
        assert DispatcherOutput.model_validate_json(out.model_dump_json()) == out


class TestIntegratorOutput:
    def test_given_required_fields_when_instantiated_then_changes_made_defaults_empty(self):
        out = IntegratorOutput(
            target_change_set_name="CS7",
            revised_steps=[ChangeSetStep(description="Add a new interface")],
        )
        assert out.target_change_set_name == "CS7"
        assert len(out.revised_steps) == 1
        assert out.changes_made == []

    def test_given_missing_revised_steps_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            IntegratorOutput(target_change_set_name="CS7")

    def test_given_missing_target_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            IntegratorOutput(revised_steps=[])

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        out = IntegratorOutput(
            target_change_set_name="CS7",
            revised_steps=[
                ChangeSetStep(description="Add interface A"),
                ChangeSetStep(description="Add interface B"),
            ],
            changes_made=[
                "Inserted step for interface A ahead of existing implementation step",
                "Reworded step 3 to reference new naming",
            ],
        )
        assert IntegratorOutput.model_validate_json(out.model_dump_json()) == out
