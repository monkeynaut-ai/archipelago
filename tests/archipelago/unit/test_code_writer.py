"""CodeWriter agent — prompt building and output mapping tests."""

from unittest.mock import MagicMock

from archipelago.agents.code_writer import CodeWriter
from archipelago.docker_worker.lifecycle import LifecycleResult
from archipelago.models import CurrentTask


def _mock_lifecycle(
    output_lines: list[str] | None = None,
    exit_code: int = 0,
    commit_hash: str = "def456",
) -> MagicMock:
    lifecycle = MagicMock()
    lifecycle.execute.return_value = LifecycleResult(
        output_lines=output_lines or ["implementation complete"],
        exit_code=exit_code,
        commit_hash=commit_hash,
    )
    return lifecycle


def _valid_state() -> dict:
    task = CurrentTask(
        objective="Add user authentication",
        title="Add login endpoint",
        acceptance_criteria=["POST /login returns JWT", "invalid credentials return 401"],
        test_focus="auth edge cases",
        implementation_focus="src/auth/login.py",
    )
    return {
        "current_task": task.model_dump(),
        "workspace_volume": "archipelago-123",
    }


class TestCodeWriter:
    def test_given_current_task_when_prompt_built_then_includes_acceptance_criteria_and_implementation_focus(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)

        agent(_valid_state(), node_config={})

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert "POST /login returns JWT" in prompt
        assert "invalid credentials return 401" in prompt
        assert "src/auth/login.py" in prompt

    def test_given_node_config_when_prompt_built_then_preamble_prepended(self):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)
        node_config = {
            "prompt_preamble": [
                "Implement production code to make the new and modified tests pass."
            ],
        }

        agent(_valid_state(), node_config=node_config)

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert prompt.startswith(
            "Implement production code to make the new and modified tests pass."
        )

    def test_given_lifecycle_completes_when_called_then_worker_result_in_state(self):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"] is not None
        assert result["worker_result"]["status"] == "completed"

    def test_given_lifecycle_completes_when_called_then_commit_hash_in_state(self):
        lifecycle = _mock_lifecycle(commit_hash="def456")
        agent = CodeWriter(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["commit_hash"] == "def456"

    def test_given_lifecycle_fails_when_called_then_status_is_failed(self):
        lifecycle = _mock_lifecycle(exit_code=1)
        agent = CodeWriter(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "failed"

    def test_given_task_with_repo_url_when_called_then_lifecycle_receives_extra_env_with_repo_url(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)
        state = _valid_state()
        state["current_task"]["repo_url"] = "https://github.com/org/repo"
        del state["workspace_volume"]

        agent(state, node_config={})

        extra_env = lifecycle.execute.call_args[1]["extra_env"]
        assert extra_env["REPO_URL"] == "https://github.com/org/repo"

    def test_given_worker_constraints_in_state_when_called_then_lifecycle_receives_constraints(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)
        state = _valid_state()
        state["worker_constraints"] = {"timeout_seconds": 1800, "mem_limit_mb": 1024}

        agent(state, node_config={})

        constraints = lifecycle.execute.call_args[1]["constraints"]
        assert constraints.timeout_seconds == 1800
        assert constraints.mem_limit_mb == 1024

    def test_given_node_config_with_readonly_dirs_when_called_then_lifecycle_receives_lockdown_env(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = CodeWriter(lifecycle=lifecycle)
        node_config = {"acp_readonly_dirs": ["/workspace/tests"]}

        agent(_valid_state(), node_config=node_config)

        extra_env = lifecycle.execute.call_args[1]["extra_env"]
        assert extra_env["ACP_READONLY_DIRS"] == "/workspace/tests"
