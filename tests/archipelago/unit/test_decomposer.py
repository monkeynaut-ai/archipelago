"""Decomposer handler — unit tests."""

import pytest

from archipelago.agents.decomposer import decomposer_handler


def _valid_job_definition() -> dict:
    return {
        "objective": "Add user authentication",
        "repo_url": "https://github.com/org/repo",
        "constraints": ["Must use OAuth2"],
        "commits": [
            {
                "title": "Add auth models",
                "acceptance_criteria": ["User model exists"],
                "test_focus": "Model validation",
                "implementation_focus": "Pydantic models",
            },
            {
                "title": "Add auth endpoints",
                "acceptance_criteria": ["Login works"],
                "test_focus": "API tests",
                "implementation_focus": "Route handlers",
            },
        ],
    }


class TestDecomposerHandler:
    def test_given_valid_job_definition_when_called_then_returns_global_context(self):
        state = {"job_definition": _valid_job_definition()}
        result = decomposer_handler(state)
        assert result["global_context"]["objective"] == "Add user authentication"
        assert result["global_context"]["constraints"] == ["Must use OAuth2"]

    def test_given_valid_job_definition_when_called_then_returns_commit_slices(self):
        state = {"job_definition": _valid_job_definition()}
        result = decomposer_handler(state)
        assert len(result["commit_slices"]) == 2
        assert result["commit_slices"][0]["title"] == "Add auth models"
        assert result["commit_slices"][1]["title"] == "Add auth endpoints"

    def test_given_valid_job_definition_when_called_then_current_index_is_zero(self):
        state = {"job_definition": _valid_job_definition()}
        result = decomposer_handler(state)
        assert result["current_index"] == 0

    def test_given_missing_job_definition_when_called_then_raises_value_error(self):
        with pytest.raises(ValueError, match="job_definition is required"):
            decomposer_handler({})

    def test_given_job_definition_with_empty_commits_when_called_then_raises(self):
        state = {"job_definition": {"objective": "test", "repo_url": "https://github.com/org/repo", "commits": []}}
        with pytest.raises(Exception, match="commits must not be empty"):
            decomposer_handler(state)
