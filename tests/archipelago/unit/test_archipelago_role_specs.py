"""Archipelago role specs — loading, schema validation, and registry integration."""

from pathlib import Path

from agent_foundry.registry.spec import RoleSpec, load_role_spec

PRODUCT_ROLES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "roles"

ARCHIPELAGO_SPEC_NAMES = [
    "code_implement_from_tests",
    "decompose_job_specification",
    "dispatch_commit",
    "evaluate_commit",
    "software_review",
    "write_unit_tests_from_spec",
]


class TestDispatchCommitSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "dispatch_commit.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "dispatch_commit"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags

    def test_given_dispatch_spec_when_loaded_then_schemas_are_none(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "dispatch_commit.yaml")
        assert spec.inputs_schema is None
        assert spec.outputs_schema is None


# ── Unit test writer and code writer specs ──


class TestUnitTestWriterSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "write_unit_tests_from_spec.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "write_unit_tests_from_spec"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags
        assert "unit-test" in spec.tags


class TestCodeWriterSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "code_implement_from_tests"
        assert spec.version == "1.0.0"
        assert "archipelago" in spec.tags


# ── Commit 3: Registry integration and tag search ──


class TestRegistryIntegration:
    def test_given_all_yaml_specs_when_registry_loaded_then_contains_15_capabilities(
        self, registry
    ):
        assert len(registry) == 14

    def test_given_registry_when_searched_by_archipelago_tag_then_returns_exactly_7(self, registry):
        results = registry.search(tags=["archipelago"])
        assert len(results) == 6

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
