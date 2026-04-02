"""Decomposer handler — unit tests."""

import pytest

from archipelago.agents.decomposer import decomposer_handler


def _valid_job_specification() -> dict:
    return {
        "objective": "Add user authentication",
        "repo_url": "https://github.com/org/repo",
        "constraints": ["Must use OAuth2"],
        "change_sets": [
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
    def test_given_valid_job_specification_when_called_then_returns_flat_job_fields(self):
        state = {"job_specification": _valid_job_specification()}
        result = decomposer_handler(state)
        assert result["objective"] == "Add user authentication"
        assert result["repo_url"] == "https://github.com/org/repo"
        assert result["repo_ref"] == "main"
        assert result["constraints"] == ["Must use OAuth2"]

    def test_given_valid_job_specification_when_called_then_returns_commit_slices(self):
        state = {"job_specification": _valid_job_specification()}
        result = decomposer_handler(state)
        assert len(result["commit_slices"]) == 2
        assert result["commit_slices"][0]["title"] == "Add auth models"
        assert result["commit_slices"][1]["title"] == "Add auth endpoints"

    def test_given_valid_job_specification_when_called_then_current_index_is_zero(self):
        state = {"job_specification": _valid_job_specification()}
        result = decomposer_handler(state)
        assert result["current_index"] == 0

    def test_given_missing_job_specification_when_called_then_raises_value_error(self):
        with pytest.raises(ValueError, match="job_specification is required"):
            decomposer_handler({})
