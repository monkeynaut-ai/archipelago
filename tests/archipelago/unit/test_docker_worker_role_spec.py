"""Docker worker role spec — loading and registry tests."""

from pathlib import Path

from agent_foundry.registry.spec import RoleSpec, load_role_spec

PRODUCT_ROLES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "roles"


class TestCodingSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "code_implement_from_tests"
        assert spec.version == "1.0.0"
        assert "docker-worker" in spec.tags

    def test_given_coding_spec_when_loaded_then_schemas_are_none(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "code_implement_from_tests.yaml")
        assert spec.inputs_schema is None
        assert spec.outputs_schema is None


class TestRegistryIntegration:
    def test_given_registry_when_searched_by_docker_worker_tag_then_returns_coding_spec(
        self, registry
    ):
        results = registry.search(tags=["docker-worker"])
        names = [s.name for s in results]
        assert "code_implement_from_tests" in names
