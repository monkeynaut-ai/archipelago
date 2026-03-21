"""Archipelago role specs — loading, schema validation, and registry integration."""

import jsonschema

from agent_foundry.registry.spec import RoleSpec, load_role_spec
from archipelago.models import (
    TestResults,
)

from pathlib import Path

PRODUCT_ROLES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "roles"

ARCHIPELAGO_SPEC_NAMES = [
    "code_implement_from_tests",
    "coding_implement_feature_from_spec",
    "decompose_job_definition",
    "dev_implement_feature_tdd",
    "dispatch_commit",
    "evaluate_commit",
    "write_unit_tests_from_spec",
]


def _valid_test_results_dump() -> dict:
    return TestResults(
        feature_name="Test Feature",
        tests_passed=5,
        tests_failed=0,
        test_output="5 passed",
        all_green=True,
    ).model_dump()


class TestDevSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "dev_implement_feature_tdd.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "dev_implement_feature_tdd"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags

    def test_given_dev_spec_when_outputs_schema_validates_model_dump_then_passes(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "dev_implement_feature_tdd.yaml")
        data = {
            "code_patch": {
                "feature_name": "Test",
                "files_changed": ["f.py"],
                "diff_summary": "diff",
                "branch_name": "feat/t",
            },
            "test_results": _valid_test_results_dump(),
        }
        jsonschema.validate(data, spec.outputs_schema)


# ── Unit test writer and code writer specs ──


class TestUnitTestWriterSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "write_unit_tests_from_spec.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "write_unit_tests_from_spec"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags
        assert "unit-test" in spec.tags

    def test_given_spec_when_outputs_schema_validates_then_passes(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "write_unit_tests_from_spec.yaml")
        data = {
            "result_summary": "Tests written",
            "workspace_ref": "/workspace",
            "workspace_volume": "archipelago-123",
            "patches": [],
            "evidence": [],
            "status": "completed",
        }
        jsonschema.validate(data, spec.outputs_schema)


class TestCodeWriterSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "code_implement_from_tests"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags

    def test_given_spec_when_inputs_require_workspace_volume(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        assert "workspace_volume" in spec.inputs_schema["required"]

    def test_given_spec_when_outputs_schema_validates_then_passes(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        data = {
            "result_summary": "Code implemented",
            "workspace_ref": "/workspace",
            "patches": [],
            "evidence": [],
            "status": "completed",
        }
        jsonschema.validate(data, spec.outputs_schema)


# ── Commit 3: Registry integration and tag search ──


class TestRegistryIntegration:
    def test_given_all_yaml_specs_when_registry_loaded_then_contains_15_capabilities(
        self, registry
    ):
        assert len(registry) == 15

    def test_given_registry_when_searched_by_archipelago_tag_then_returns_exactly_7(self, registry):
        results = registry.search(tags=["archipelago"])
        assert len(results) == 7

    def test_given_each_archipelago_spec_when_name_queried_then_found_in_registry(self, registry):
        for name in ARCHIPELAGO_SPEC_NAMES:
            assert registry.get(name) is not None, f"Missing role: {name}"

    def test_given_archipelago_tag_search_then_results_sorted_by_name(self, registry):
        results = registry.search(tags=["archipelago"])
        names = [s.name for s in results]
        assert names == sorted(names)

    def test_given_archipelago_tag_search_then_returns_only_archipelago_specs(self, registry):
        results = registry.search(tags=["archipelago"])
        names = {s.name for s in results}
        assert names == set(ARCHIPELAGO_SPEC_NAMES)
