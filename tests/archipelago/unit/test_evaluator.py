"""Evaluator handler — unit tests."""

from archipelago.agents.evaluator import evaluator_handler


class TestEvaluatorHandler:
    def test_given_any_state_when_called_then_commit_passed_is_true(self):
        result = evaluator_handler({"current_commit": {"title": "c1"}})
        assert result["commit_passed"] is True

    def test_given_state_when_called_then_existing_state_preserved(self):
        result = evaluator_handler({"current_commit": {"title": "c1"}, "other": "data"})
        assert result["other"] == "data"
