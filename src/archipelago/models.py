"""Canonical artifact models for the Archipelago pipeline."""

from pydantic import BaseModel, field_validator


class CommitSlice(BaseModel):
    title: str
    acceptance_criteria: list[str] = []
    test_focus: str = ""
    implementation_focus: str = ""


class JobDefinition(BaseModel):
    objective: str
    constraints: list[str] = []
    commits: list[CommitSlice]

    @field_validator("commits")
    @classmethod
    def _commits_not_empty(cls, v: list[CommitSlice]) -> list[CommitSlice]:
        if not v:
            raise ValueError("commits must not be empty")
        return v


class CodePatch(BaseModel):
    feature_name: str
    files_changed: list[str]
    diff_summary: str
    branch_name: str


class TestResults(BaseModel):
    __test__ = False

    feature_name: str
    tests_passed: int
    tests_failed: int
    test_output: str
    all_green: bool
