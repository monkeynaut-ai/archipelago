"""SoftwareReviewer agent — prompt building, output mapping, and review parsing tests."""

import json
from unittest.mock import MagicMock

from archipelago.agents.software_reviewer import SoftwareReviewer, _review_output_path
from archipelago.docker_worker.lifecycle import LifecycleResult
from archipelago.models import CurrentTask

COMMIT_HASH = "def456"
EXPECTED_REVIEW_PATH = f"/workspace/review-{COMMIT_HASH}.json"


def _valid_review_json() -> dict:
    return {
        "scope": {
            "paths": ["src/auth/login.py"],
            "commit_range": "abc..def",
        },
        "summary": {
            "overall_rating": "good",
            "strengths": ["Clean code"],
            "primary_concerns": [],
        },
        "findings": [],
    }


def _mock_lifecycle(
    output_lines: list[str] | None = None,
    exit_code: int = 0,
    commit_hash: str = "abc123",
    collected_files: dict[str, str] | None = None,
) -> MagicMock:
    lifecycle = MagicMock()
    lifecycle.execute.return_value = LifecycleResult(
        output_lines=output_lines or ["review complete"],
        exit_code=exit_code,
        commit_hash=commit_hash,
        collected_files=collected_files or {},
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
        "commit_hash": COMMIT_HASH,
    }


class TestSoftwareReviewer:
    def test_given_commit_hash_when_prompt_built_then_includes_commit_hash(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        agent(_valid_state(), node_config={})

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert COMMIT_HASH in prompt

    def test_given_commit_hash_when_prompt_built_then_includes_review_output_path(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        agent(_valid_state(), node_config={})

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert EXPECTED_REVIEW_PATH in prompt

    def test_given_node_config_when_prompt_built_then_preamble_prepended(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)
        node_config = {
            "prompt_preamble": ["Review the changes in the commit hash given below."],
        }

        agent(_valid_state(), node_config=node_config)

        prompt = lifecycle.execute.call_args[1]["prompt"]
        assert prompt.startswith("Review the changes in the commit hash given below.")

    def test_given_lifecycle_completes_with_review_file_when_called_then_review_parsed(self):
        review = _valid_review_json()
        lifecycle = _mock_lifecycle(
            collected_files={EXPECTED_REVIEW_PATH: json.dumps(review)},
        )
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "completed"
        assert result["worker_result"]["review"] is not None
        assert result["worker_result"]["review"]["summary"]["overall_rating"] == "good"

    def test_given_lifecycle_completes_without_review_file_when_called_then_review_is_none(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["review"] is None

    def test_given_invalid_review_json_when_called_then_status_is_failed(self):
        lifecycle = _mock_lifecycle(
            collected_files={EXPECTED_REVIEW_PATH: "not valid json"},
        )
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "failed"
        assert result["worker_result"]["review"] is None

    def test_given_review_with_wrong_schema_when_called_then_status_is_failed(self):
        bad_review = {"scope": "not an object", "summary": "bad", "findings": "bad"}
        lifecycle = _mock_lifecycle(
            collected_files={EXPECTED_REVIEW_PATH: json.dumps(bad_review)},
        )
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "failed"

    def test_given_lifecycle_fails_when_called_then_status_is_failed(self):
        lifecycle = _mock_lifecycle(exit_code=1)
        agent = SoftwareReviewer(lifecycle=lifecycle)

        result = agent(_valid_state(), node_config={})

        assert result["worker_result"]["status"] == "failed"

    def test_given_commit_hash_when_called_then_lifecycle_collects_dynamic_review_path(self):
        lifecycle = _mock_lifecycle()
        agent = SoftwareReviewer(lifecycle=lifecycle)

        agent(_valid_state(), node_config={})

        collect_files = lifecycle.execute.call_args[1]["collect_files"]
        assert collect_files == [EXPECTED_REVIEW_PATH]

    def test_given_different_commit_hashes_when_called_then_review_paths_differ(self):
        path_a = _review_output_path("aaa111")
        path_b = _review_output_path("bbb222")
        assert path_a != path_b
        assert "aaa111" in path_a
        assert "bbb222" in path_b

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
