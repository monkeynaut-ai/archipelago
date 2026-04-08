"""Role spec YAML files — structural validation.

These tests parse each role spec file directly with PyYAML and assert the
required schema keys are present with sane values. They do not load the
Archipelago registry (which lazy-imports agent modules that may not exist
yet during the CS6 → CS7 transition).
"""

from pathlib import Path

import yaml

ROLES_DIR = Path(__file__).resolve().parents[3] / "src" / "archipelago" / "roles"

REQUIRED_TOP_LEVEL_KEYS = {
    "name",
    "description",
    "version",
    "implementation",
    "tags",
    "quality_controls",
}
REQUIRED_IMPLEMENTATION_KEYS = {"module", "class_name"}
REQUIRED_QC_KEYS = {"timeout_seconds", "max_retries"}


def _load(name: str) -> dict:
    path = ROLES_DIR / name
    assert path.is_file(), f"Role spec not found: {path}"
    with path.open() as f:
        return yaml.safe_load(f)


def _assert_schema(
    spec: dict,
    *,
    expected_name: str,
    expected_module: str,
    expected_class: str,
) -> None:
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(spec.keys()), (
        f"Missing top-level keys: {REQUIRED_TOP_LEVEL_KEYS - spec.keys()}"
    )
    assert spec["name"] == expected_name
    assert isinstance(spec["description"], str) and spec["description"]
    assert isinstance(spec["version"], str) and spec["version"]
    impl = spec["implementation"]
    assert REQUIRED_IMPLEMENTATION_KEYS.issubset(impl.keys())
    assert impl["module"] == expected_module
    assert impl["class_name"] == expected_class
    assert isinstance(spec["tags"], list) and len(spec["tags"]) > 0
    qc = spec["quality_controls"]
    assert REQUIRED_QC_KEYS.issubset(qc.keys())
    assert isinstance(qc["timeout_seconds"], int) and qc["timeout_seconds"] > 0
    assert isinstance(qc["max_retries"], int) and qc["max_retries"] >= 0


class TestExistingSoftwareReviewSpec:
    """Sanity check the harness against an already-present role spec."""

    def test_given_software_review_yaml_when_loaded_then_matches_schema(self):
        spec = _load("software_review.yaml")
        _assert_schema(
            spec,
            expected_name="software_review",
            expected_module="archipelago.agents.software_reviewer",
            expected_class="SoftwareReviewer",
        )


class TestPlanImplementationTaskSpec:
    def test_given_plan_implementation_task_yaml_when_loaded_then_matches_schema(self):
        spec = _load("plan_implementation_task.yaml")
        _assert_schema(
            spec,
            expected_name="plan_implementation_task",
            expected_module="archipelago.agents.planner",
            expected_class="Planner",
        )


class TestReviewChangeSetSpec:
    def test_given_review_change_set_yaml_when_loaded_then_matches_schema(self):
        spec = _load("review_change_set.yaml")
        _assert_schema(
            spec,
            expected_name="review_change_set",
            expected_module="archipelago.agents.reviewer",
            expected_class="Reviewer",
        )


class TestDispatchFindingsSpec:
    def test_given_dispatch_findings_yaml_when_loaded_then_matches_schema(self):
        spec = _load("dispatch_findings.yaml")
        _assert_schema(
            spec,
            expected_name="dispatch_findings",
            expected_module="archipelago.agents.finding_dispatcher",
            expected_class="FindingDispatcher",
        )


class TestIntegrateFindingsSpec:
    def test_given_integrate_findings_yaml_when_loaded_then_matches_schema(self):
        spec = _load("integrate_findings.yaml")
        _assert_schema(
            spec,
            expected_name="integrate_findings",
            expected_module="archipelago.agents.integrator",
            expected_class="Integrator",
        )
