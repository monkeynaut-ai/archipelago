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
    lines: str | None = Field(default=None, description="Line range (e.g., '50-57', '106')")
    symbol: str | None = Field(
        default=None,
        description="Function, class, or variable name for LSP-based navigation",
    )


class CodeReviewSuggestion(BaseModel):
    approach: str = Field(
        description="Recommended fix strategy in enough detail for an agent to act"
        " without ambiguity"
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="Other valid approaches if the primary is blocked",
    )
    effort: Literal["trivial", "small", "medium", "large"] | None = Field(
        default=None,
        description="Relative size of the change — helps an agent batch or sequence work",
    )
    risk: Literal["safe", "moderate", "breaking"] | None = Field(
        default=None,
        description="safe = no behavior change; moderate = internal behavior change;"
        " breaking = public API change",
    )


class CodeReviewVerification(BaseModel):
    """How the agent confirms the fix is correct."""

    test_exists: bool | None = Field(
        default=None, description="Whether existing tests cover this area"
    )
    test_strategy: str | None = Field(
        default=None,
        description="How the agent should verify the fix (e.g., 'run existing tests',"
        " 'add test for stale data scenario')",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Concrete conditions that must be true after the fix",
    )


class CodeReviewFinding(BaseModel):
    id: str = Field(
        description="Stable identifier for cross-referencing (e.g., 'F1', 'coupling-01')"
    )
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
    ] = Field(description="Which design quality this finding relates to")
    severity: Literal["critical", "major", "minor", "informational"] = Field(
        description="critical = causes bugs or data loss; major = structural problem"
        " that compounds; minor = improvement opportunity;"
        " informational = observation only"
    )
    title: str = Field(description="One-line summary an agent can use as a commit message seed")
    problem: str = Field(
        description="What is wrong and why it matters — the agent uses this to validate"
        " its fix actually addresses the root cause"
    )
    locations: list[CodeReviewLocation] = Field(
        description="Where in the code this problem manifests"
    )
    suggestion: CodeReviewSuggestion
    verification: CodeReviewVerification | None = Field(
        default=None, description="How the agent confirms the fix is correct"
    )


class CodeReviewScope(BaseModel):
    """What was reviewed."""

    paths: list[str] = Field(description="Files or directories included in the review")
    commit_range: str | None = Field(default=None, description="Git commit range reviewed")
    context: str | None = Field(default=None, description="Why this review was conducted")


class CodeReviewSummary(BaseModel):
    """High-level assessment an agent reads first to prioritize."""

    overall_rating: Literal["good", "acceptable", "needs_work", "critical"] = Field(
        description="Coarse signal for triage — should the agent act now or move on"
    )
    strengths: list[str] = Field(description="What to preserve — an agent must not regress these")
    primary_concerns: list[str] = Field(description="Top-level problems in plain language")


class CodeReviewConstraints(BaseModel):
    """Boundaries the agent must respect when acting on findings."""

    preserve: list[str] = Field(
        default_factory=list,
        description="Invariants that must not be broken"
        " (e.g., 'public API signatures', 'test count')",
    )
    avoid: list[str] = Field(
        default_factory=list,
        description="Anti-patterns or approaches to reject"
        " (e.g., 'no ORM introduction', 'no new dependencies')",
    )
    dependencies: list[dict[str, str]] = Field(
        default_factory=list,
        description="Execution order constraints between findings",
    )


class CodeReview(BaseModel):
    """Structured code review an AI agent uses to guide refactoring."""

    scope: CodeReviewScope
    summary: CodeReviewSummary
    findings: list[CodeReviewFinding] = Field(
        description="Individual actionable observations, ordered by priority"
    )
    constraints: CodeReviewConstraints | None = None
