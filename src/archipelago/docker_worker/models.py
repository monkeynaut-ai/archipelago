"""Data models for the Docker worker subsystem."""

from typing import Literal

from pydantic import BaseModel, Field

from archipelago.models import CommitSpecification
from archipelago.types import Objective, RepoRef, RepoUrl, WorkSpace


class WorkerConstraints(BaseModel):
    """Resource and policy constraints for a Docker worker run."""

    timeout_seconds: int = Field(default=3600, description="Max wall-clock seconds for the run")
    max_cost_usd: float | None = Field(
        default=None, description="Spending cap for this worker invocation"
    )
    allowed_commands: list[str] = Field(
        default_factory=list, description="Shell commands the agent may execute"
    )
    network_policy: str = Field(
        default="none", description="Network access policy: 'none', 'limited', or 'full'"
    )
    mem_limit_mb: int = Field(default=512, description="Container memory limit in MB")
    cpu_quota: int | None = Field(default=None, description="CPU quota for the container")
    pids_limit: int | None = Field(default=None, description="Max number of processes")
    turn_timeout_seconds: int = Field(
        default=3600, description="Max seconds for a single agent turn"
    )
    skip_permissions: bool = Field(default=False, description="Whether to skip permission prompts")
    connection_timeout_seconds: int = Field(
        default=120, description="Max seconds to wait for container connection"
    )


class WorkerInput(BaseModel):
    """Typed input for docker worker roles."""

    # Task data — what to work on (flows through state from the archipelago flow)
    commit_spec: CommitSpecification = Field(description="Specification for the commit to produce")
    objective: Objective = Field(default="", description="High-level goal for the pipeline run")
    constraints_text: list[str] = Field(
        default_factory=list, description="Rules the agent must follow"
    )
    repo_ref: RepoRef = Field(description="Branch or tag to work on")
    repo_url: RepoUrl | None = Field(
        default=None, description="Git remote URL of the target repository"
    )

    # Node config — static per-node settings (from archipelago_system.json via closure)
    acp_hidden_dirs: list[str] = Field(
        default_factory=list, description="Directories hidden from the agent"
    )
    acp_readonly_dirs: list[str] = Field(
        default_factory=list, description="Directories the agent cannot modify"
    )
    role_instructions_path: str | None = Field(
        default=None, description="Path to role-specific instruction markdown"
    )
    prompt_preamble: list[str] = Field(
        default_factory=list, description="Lines prepended to the agent prompt"
    )

    # Runtime state — changes during execution, shared between nodes
    constraints: WorkerConstraints = Field(description="Resource and policy constraints")
    workspace_volume: WorkSpace | None = Field(
        default=None, description="Docker volume holding the working copy"
    )


class PatchInfo(BaseModel):
    """Metadata about a patch/PR produced by the worker."""

    pr_id: str
    branch_name: str
    files_changed: list[str]
    diff_summary: str


class CommitEvidence(BaseModel):
    """Evidence collected for a single commit."""

    commit_id: str
    pr_id: str
    test_commands_run: list[str]
    test_output: str
    tests_passed: int
    tests_failed: int
    all_green: bool


class WorkerResult(BaseModel):
    """Typed output from the coding.implement_feature_from_spec role."""

    result_summary: str
    workspace_ref: str
    patches: list[PatchInfo]
    evidence: list[CommitEvidence]
    status: Literal["completed", "failed", "interrupted", "timed_out"]


class TestRunRecord(BaseModel):
    """Record of a single test command execution."""

    __test__ = False

    command: str
    exit_code: int
    output_summary: str


class ProgressEvent(BaseModel):
    """A structured progress checkpoint emitted by CC to progress.jsonl."""

    type: Literal["commit_started", "commit_green", "pr_completed", "blocked"]
    pr_id: str
    commit_id: str
    files_changed: list[str] = Field(default_factory=list)
    tests_added: list[str] = Field(default_factory=list)
    tests_run: list[TestRunRecord] = Field(default_factory=list)
    status: str
    notes: str = ""
    timestamp: float


class ClarificationRequest(BaseModel):
    """Parsed payload from ARCHIPELAGO_NEED_CLARIFICATION marker."""

    question: str
    options: list[str] = Field(default_factory=list)
    default: str | None = None
    blocking: bool = True


class PermissionRequest(BaseModel):
    """Parsed payload from ARCHIPELAGO_NEED_PERMISSION marker."""

    action: str
    risk_level: Literal["low", "medium", "high"]
    why_needed: str
    alternatives: list[str] = Field(default_factory=list)


class UpdateAvailable(BaseModel):
    """Parsed payload from ARCHIPELAGO_UPDATE_AVAILABLE marker."""

    installed: str
    latest: str


class ResumePoint(BaseModel):
    """Identifies where to resume work after a crash or pause."""

    pr_id: str
    commit_id: str
    status: str
