"""SoftwareReviewer agent — prompt building and output mapping tests."""

from unittest.mock import MagicMock

from archipelago.agents.software_reviewer import SoftwareReviewer
from archipelago.docker_worker.lifecycle import LifecycleResult
from archipelago.models import CurrentTask


def _mock_lifecycle(
    output_lines: list[str] | None = None,
    exit_code: int = 0,
    commit_hash: str = "abc123",
) -> MagicMock:
    lifecycle = MagicMock()
    lifecycle.execute.return_value = LifecycleResult(
        output_lines=output_lines or ["review complete"],
        exit_code=exit_code,
        commit_hash=commit_hash,
    )
    return lifecycle


def _valid_state() -> dict:
    task = CurrentTask(
        objective="Add user authentication",
        title="Add login endpoint",
        acceptance_criteria=["POST /login returns JWT"],
    )
    return {
        "current_task": task.model_dump(),
        "workspace_volume": "archipelago-123",
        "commit_hash": "def456",
    }


class TestSoftwareReviewer:
    def test_given_commit_hash_when_prompt_built_then_includes_commit_hash(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        agent(_valid_state(), node_config={})

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert "def456" in prompt

    def test_given_node_config_when_prompt_built_then_preamble_prepended(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)
        node_config = {
            "prompt_preamble": ["Review the changes in the commit hash given below."],
        }

        agent(_valid_state(), node_config=node_config)

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert prompt.startswith("Review the changes in the commit hash given below.")

    def test_given_lifecycle_completes_when_called_then_worker_result_in_state(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"] is not None
        assert result["worker_result"]["status"] == "completed"

    def test_given_lifecycle_fails_when_called_then_status_is_failed(self):
        lifecycle = _mock_lifecycle(exit_code=1)
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "failed"

    def test_given_worker_constraints_in_state_when_called_then_lifecycle_receives_constraints(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)
        state = _valid_state()
        state["worker_constraints"] = {"timeout_seconds": 1800, "mem_limit_mb": 1024}

        agent(state, node_config={})

        constraints = lifecycle.execute.call_args[1]["constraints"]
        assert constraints.timeout_seconds == 1800
        assert constraints.mem_limit_mb == 1024

    def test_given_node_config_with_role_instructions_when_called_then_lifecycle_receives_lockdown_env(
        self,
    ):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)
        node_config = {
            "role_instructions_path": "/home/claude/.claude/CLAUDE-software-review.md",
        }

        agent(_valid_state(), node_config=node_config)

        extra_env = lifecycle.execute.call_args[1]["extra_env"]
        assert (
            extra_env["ACP_ROLE_INSTRUCTIONS_PATH"]
            == "/home/claude/.claude/CLAUDE-software-review.md"
        )
