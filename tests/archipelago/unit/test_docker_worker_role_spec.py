"""Docker worker role spec — loading, schema validation, and registry tests."""

import jsonschema

from agent_foundry.registry.spec import RoleSpec, load_role_spec
from archipelago.docker_worker.models import WorkerConstraints, WorkerInput, WorkerResult

from pathlib import Path

PRODUCT_ROLES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "roles"


class TestCodingSpec:
    def test_given_yaml_file_when_loaded_then_returns_valid_role_spec(self):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "coding_implement_feature_from_spec.yaml")
        assert isinstance(spec, RoleSpec)
        assert spec.name == "coding_implement_feature_from_spec"
        assert spec.version == "1.0.0"
        assert "docker-worker" in spec.tags

    def test_given_coding_spec_when_inputs_schema_validates_subgraph_state_then_passes(
        self,
    ):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "coding_implement_feature_from_spec.yaml")
        subgraph_state = {
            "current_commit": {"title": "test", "repo_url": "https://github.com/org/repo", "repo_ref": "main"},
        }
        jsonschema.validate(subgraph_state, spec.inputs_schema)

    def test_given_coding_spec_when_outputs_schema_validates_worker_result_then_passes(
        self,
    ):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "coding_implement_feature_from_spec.yaml")
        data = {
            "worker_result": {"result_summary": "done", "status": "completed"},
            "workspace_volume": "archipelago-123",
        }
        jsonschema.validate(data, spec.outputs_schema)


class TestRegistryIntegration:
    def test_given_registry_when_searched_by_docker_worker_tag_then_returns_coding_spec(
        self, registry
    ):
        results = registry.search(tags=["docker-worker"])
        names = [s.name for s in results]
        assert "coding_implement_feature_from_spec" in names
