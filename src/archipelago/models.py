"""Canonical artifact models for the Archipelago pipeline."""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from archipelago.types import Objective, RepoRef, RepoUrl


class FeatureDefinition(BaseModel):
    """
    A FeatureDefinition defines the business case for a feature enhancement or enablement.

    It will be transformed into a JobSpecification.
    """

    id: str = Field(description="The id of the feature definition")
    name: str = Field(description="Concise name that conveys the capability being enabled")
    problem_statement: str = Field(
        description="crisp articulation of the user or business problem this feature solves"
    )
    feature_intent: str = Field(
        description="A single declarative statement of what this feature is meant to achieve. \
            This is the north star for all work on this feature."
    )
    desired_outcomes: list[str] = Field(
        default_factory=list,
        description="Express outcomes as observable or measurable states, not activities.",
    )
    # success_metrics: list[str] = Field(default_factory=list, description="Define 2-4 specific,
    # measurable indicators that would confirm this feature is succeeding. Align these to metrics
    # already defined in the product compass where possible. Include: Metric name Direction of
    # change (increase/decrease/achieve) Indicative target or threshold if determinable from
    # compass context")
    scope_boundaries: list[str] = Field(
        default_factory=list,
        description="Explicit statement of what is out of scope for this feature.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Key assumptions that must hold for this feature to deliver its intended \
            outcomes",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Dependencies on other features, platform capabilities, data, or third parties",
    )
    value_hypothesis: str = Field(
        description="A testable claim of how achieving the objective will create meaningful \
            impact. Keep focus on impact, not implementation."
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints that must be followed when implementing this feature definition",
    )
    rules: list[str] = Field(
        default_factory=list,
        description="Rules that must be followed when implementing this feature definition",
    )


class JobSpecification(BaseModel):
    """
    A JobSpecification specifies changes that implement a feature definition (or fix, refactor,
    enhancement).
    """

    # id: str = Field(description="The id of the job")
    repo_url: RepoUrl = Field(description="Git remote URL of the target repository")
    repo_ref: RepoRef = Field(default="main", description="Branch or tag to work on")
    objective: Objective = Field(description="High-level goal for the pipeline run")
    # scope, constraints, rules
    constraints: list[str] = Field(default_factory=list, description="Rules all agents must follow")
    test_paths: list[str] = Field(
        default_factory=list,
        description="Directories containing test code (for write-permission enforcement). "
        "Will move to a repo-level Archipelago config in a future version.",
    )
    change_sets: list[ChangeSet] = Field(description="The change sets of the job")


class ChangeSetStep(BaseModel):
    """An atomic unit of work inside a ChangeSet."""

    description: str = Field(description="What to do in this step")
    acceptance_criteria_addressed: list[str] = Field(
        default_factory=list,
        description="Copies of the parent ChangeSet acceptance criteria this step addresses",
    )


class Severity(StrEnum):
    """Review finding severity — drives review-fix cycle routing."""

    MUST_FIX = "must_fix"
    CAN_DEFER = "can_defer"


class ReviewFinding(BaseModel):
    """A single finding produced by the Reviewer agent."""

    description: str = Field(description="What the issue is")
    severity: Severity = Field(
        description="must_fix = blocks merge and enters the review-fix cycle; "
        "can_defer = routed post-PR by the Dispatcher",
    )
    category: str = Field(
        description="Short category label for the finding. Prefer one of: "
        "design_quality, code_quality, test_complexity, naming. "
        "Use a different label only if none of these fit.",
    )
    affected_files_and_locations: list[str] = Field(
        default_factory=list,
        description="Where in the code the finding applies (file:line or file:symbol)",
    )
    suggested_resolution: str = Field(
        default="",
        description="What the Reviewer proposes changing to resolve the finding",
    )
    source_commit_hashes: list[str] = Field(
        default_factory=list,
        description="Commits that introduced the issue",
    )


class ReviewerPayload(BaseModel):
    """Reviewer agent's structured-output payload.

    Thin wrapper around a list of ReviewFindings. Exists because the
    ``--json-schema`` enforcement path (CS6.5) and Pydantic's
    ``model_json_schema`` both require a top-level object, not a bare
    list. Used by CS7's Reviewer handler as the ``T`` in
    ``AgentTurnEnvelope[T]``.
    """

    findings: list[ReviewFinding] = Field(
        default_factory=list,
        description=(
            "All review findings produced in this review pass — must_fix and "
            "can_defer together. Severity is carried on each finding; the "
            "Runner filters/branches downstream, so the Reviewer does not "
            "pre-split them."
        ),
    )


class OriginKind(StrEnum):
    """Tag identifying which origin variant wraps an ImplementationTask source."""

    STEP = "step"
    FINDING = "finding"


class StepOrigin(BaseModel):
    """Forward-looking task origin: a planned ChangeSetStep."""

    kind: Literal[OriginKind.STEP] = OriginKind.STEP
    step: ChangeSetStep


class FindingOrigin(BaseModel):
    """Backward-looking task origin: a ReviewFinding to fix."""

    kind: Literal[OriginKind.FINDING] = OriginKind.FINDING
    finding: ReviewFinding


TaskOrigin = Annotated[
    StepOrigin | FindingOrigin,
    Field(discriminator="kind"),
]


class ImplementationTask(BaseModel):
    """Planner output — the unit of work consumed by the Test Agent and Implementer."""

    origin: TaskOrigin = Field(description="Either a ChangeSetStep or a ReviewFinding")
    interface_specifications: list[str] = Field(
        default_factory=list,
        description="Function signatures, data shapes, contracts introduced or modified",
    )
    unit_test_changes: list[str] = Field(
        default_factory=list,
        description="Test behaviors to add or remove, each mapped to an acceptance criterion",
    )
    implementation_change: str = Field(
        description="Behavioral description of the software change needed",
    )


class Disposition(StrEnum):
    """Dispatcher routing decision for a single review finding."""

    ROUTE_TO_CHANGE_SET = "route_to_change_set"
    DEFER_TO_POST_JOB = "defer_to_post_job"
    ESCALATE = "escalate"


class DispatchedFinding(BaseModel):
    """A routing decision for a single review finding."""

    finding: ReviewFinding
    disposition: Disposition
    target_change_set_name: str | None = Field(
        default=None,
        description="Target change set when disposition is ROUTE_TO_CHANGE_SET",
    )
    rationale: str = Field(description="Why the Dispatcher chose this routing")


class DispatcherOutput(BaseModel):
    """Categorized output from the Dispatcher agent."""

    routed_findings: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings routed to specific change sets",
    )
    deferred_findings: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings deferred to the post-job report",
    )
    escalations: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings requiring human routing decisions",
    )


class IntegratorOutput(BaseModel):
    """Revised step sequence for a change set after Integrator processing."""

    target_change_set_name: str = Field(description="Which change set was revised")
    revised_steps: list[ChangeSetStep] = Field(
        description="Updated ordered list of Change Set Steps",
    )
    changes_made: list[str] = Field(
        default_factory=list,
        description="Natural-language descriptions of what was inserted, modified, "
        "reordered, or removed, and why",
    )


class ChangeSet(BaseModel):
    """A cohesive unit of work in a job specification."""

    name: str = Field(description="Short title — used as the PR title")
    intent: str = Field(description="Purpose and motivation for this change set")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Success conditions for this change set",
    )
    interface_specifications: list[str] | None = Field(
        default=None,
        description="Contracts (signatures, data shapes) this change set introduces or modifies",
    )
    steps: list[ChangeSetStep] = Field(
        default_factory=list,
        description="Ordered list of change set steps",
    )


class CurrentTask(BaseModel):
    """The current unit of work flowing through the implementation kernel.

    Combines job-level context (objective, repo, constraints) with
    commit-level specification (title, acceptance criteria, focus areas).
    """

    objective: Objective = Field(description="High-level goal for the pipeline run")
    repo_url: RepoUrl | None = Field(
        default=None, description="Git remote URL of the target repository"
    )
    repo_ref: RepoRef = Field(default="main", description="Branch or tag to work on")
    constraints: list[str] = Field(default_factory=list, description="Rules the agent must follow")
    title: str = Field(description="Commit title describing this unit of work")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions that must be true for this task to pass",
    )
    test_focus: str = Field(default="", description="What the tests should exercise")
    implementation_focus: str = Field(
        default="", description="Where implementation effort should concentrate"
    )


class TestResults(BaseModel):
    __test__ = False

    feature_name: str
    tests_passed: int
    tests_failed: int
    test_output: str
    all_green: bool


# ── Agent output models ──


class AgentWorkerResult(BaseModel):
    """Structured output from any docker-worker agent execution."""

    result_summary: str = Field(description="Human-readable summary of agent execution")
    status: Literal["completed", "failed"] = Field(description="Terminal status of the agent run")
    output_lines: list[str] = Field(
        default_factory=list, description="Raw output lines captured from the agent"
    )
    review: dict[str, Any] | None = Field(
        default=None, description="Parsed CodeReview data (present only for software_reviewer)"
    )


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
