"""Canonical artifact models for the Archipelago pipeline."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CommitSpecification(BaseModel):
    title: str
    acceptance_criteria: list[str] = []
    test_focus: str = ""
    implementation_focus: str = ""


class CurrentTask(BaseModel):
    """The current unit of work flowing through the implementation kernel.

    Combines job-level context (objective, repo, constraints) with
    commit-level specification (title, acceptance criteria, focus areas).
    """

    objective: str
    repo_url: str | None = None
    repo_ref: str = "main"
    constraints: list[str] = Field(default_factory=list)
    title: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_focus: str = ""
    implementation_focus: str = ""


class KernelState(BaseModel):
    """Typed state for the implementation kernel subgraph."""

    current_task: CurrentTask
    workspace_volume: str | None = None
    commit_hash: str | None = None
    worker_result: dict[str, Any] | None = None
    commit_passed: bool | None = None


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


# ── Code Review models ──


class CodeReviewLocation(BaseModel):
    file: str
    lines: str | None = None
    symbol: str | None = None


class CodeReviewSuggestion(BaseModel):
    approach: str
    alternatives: list[str] = Field(default_factory=list)
    effort: Literal["trivial", "small", "medium", "large"] | None = None
    risk: Literal["safe", "moderate", "breaking"] | None = None


class CodeReviewVerification(BaseModel):
    test_exists: bool | None = None
    test_strategy: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class CodeReviewFinding(BaseModel):
    id: str
    quality: Literal[
        "simplicity",
        "cohesion",
        "coupling",
        "testability",
        "clarity",
        "abstraction",
        "separation_of_concerns",
        "composability",
        "fail_fast",
        "surface_area",
        "consistency",
        "reversibility",
    ]
    severity: Literal["critical", "major", "minor", "informational"]
    title: str
    problem: str
    locations: list[CodeReviewLocation]
    suggestion: CodeReviewSuggestion
    verification: CodeReviewVerification | None = None


class CodeReviewScope(BaseModel):
    paths: list[str]
    commit_range: str | None = None
    context: str | None = None


class CodeReviewSummary(BaseModel):
    overall_rating: Literal["good", "acceptable", "needs_work", "critical"]
    strengths: list[str]
    primary_concerns: list[str]


class CodeReviewConstraints(BaseModel):
    preserve: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)


class CodeReview(BaseModel):
    scope: CodeReviewScope
    summary: CodeReviewSummary
    findings: list[CodeReviewFinding]
    constraints: CodeReviewConstraints | None = None
