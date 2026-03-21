"""Canonical artifact models for the Archipelago pipeline."""

from pydantic import BaseModel, field_validator


class CommitSpecification(BaseModel):
    title: str
    acceptance_criteria: list[str] = []
    test_focus: str = ""
    implementation_focus: str = ""


class JobDefinition(BaseModel):
    objective: str
    repo_url: str
    repo_ref: str = "main"
    constraints: list[str] = []
    commits: list[CommitSpecification]

    @field_validator("commits")
    @classmethod
    def _commits_not_empty(cls, v: list[CommitSpecification]) -> list[CommitSpecification]:
        if not v:
            raise ValueError("commits must not be empty")
        return v


class TestResults(BaseModel):
    __test__ = False

    feature_name: str
    tests_passed: int
    tests_failed: int
    test_output: str
    all_green: bool
