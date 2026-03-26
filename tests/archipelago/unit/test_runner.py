"""Tests for run_archipelago and run_dev_test with mocked graph and handler."""

from unittest.mock import MagicMock, patch

from archipelago.runner import run_archipelago, run_dev_test


class TestRunArchipelago:
    @patch("archipelago.runner.run_plan")
    @patch("archipelago.runner.load_archipelago_plan")
    def test_given_valid_input_when_called_then_invokes_run_plan_with_correct_state(
        self, mock_load_plan, mock_run_plan
    ):
        mock_plan = MagicMock()
        mock_load_plan.return_value = mock_plan

        mock_run_plan.return_value = {"commit_passed": True}

        job_def = {
            "objective": "Build a test app",
            "repo_url": "https://github.com/org/repo",
            "commits": [{"title": "c1"}],
        }
        result = run_archipelago(job_def)

        mock_run_plan.assert_called_once()
        call_kwargs = mock_run_plan.call_args
        assert call_kwargs.kwargs["initial_state"] == {"job_definition": job_def}
        assert result == {"commit_passed": True}


class TestRunDevTest:
    @patch("archipelago.agents.unit_test_writer.DockerLifecycle")
    def test_given_dev_test_input_when_called_then_agent_invoked_with_current_task(
        self, mock_lifecycle_cls
    ):
        mock_lifecycle = MagicMock()
        mock_lifecycle.execute.return_value = MagicMock(
            output_lines=["done"], exit_code=0, commit_hash="abc123"
        )
        mock_lifecycle_cls.return_value = mock_lifecycle

        dev_test_input = {
            "repo_url": "https://github.com/org/repo",
            "repo_ref": "main",
            "commit_spec": {"title": "Add login"},
        }

        result = run_dev_test(dev_test_input)

        mock_lifecycle.execute.assert_called_once()
        assert "worker_result" in result
