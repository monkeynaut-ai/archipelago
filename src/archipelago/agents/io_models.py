"""Per-agent output models for the Archipelago pipeline.

Each model defines the typed return value of a single agent. Field names
map directly to LangGraph state keys — the connector calls ``model_dump()``
to produce the dict that LangGraph merges into state.
"""

from typing import Any

from pydantic import BaseModel, Field

from archipelago.models import AgentWorkerResult, CurrentTask
from archipelago.types import CommitHash, Objective, RepoRef, RepoUrl, WorkSpace


class UnitTestWriterOutput(BaseModel):
    """Output from the unit test writer agent."""

    worker_result: AgentWorkerResult = Field(description="Execution result and captured output")
    workspace_volume: WorkSpace = Field(description="Docker volume with the working copy")


class CodeWriterOutput(BaseModel):
    """Output from the code writer agent."""

    worker_result: AgentWorkerResult = Field(description="Execution result and captured output")
    workspace_volume: WorkSpace = Field(description="Docker volume with the working copy")
    commit_hash: CommitHash = Field(description="Git SHA of the commit produced by the agent")


class SoftwareReviewerOutput(BaseModel):
    """Output from the software reviewer agent."""

    worker_result: AgentWorkerResult = Field(description="Execution result with review data")
    workspace_volume: WorkSpace = Field(description="Docker volume with the working copy")


class EvaluatorOutput(BaseModel):
    """Output from the evaluator agent."""

    commit_passed: bool = Field(description="Whether the commit met acceptance criteria")


class DecomposerOutput(BaseModel):
    """Output from the decomposer agent."""

    objective: Objective = Field(description="High-level goal extracted from the job definition")
    repo_url: RepoUrl = Field(description="Git remote URL of the target repository")
    repo_ref: RepoRef = Field(default="main", description="Branch or tag to work on")
    constraints: list[str] = Field(default_factory=list, description="Rules all agents must follow")
    commit_slices: list[dict[str, Any]] = Field(
        description="Ordered list of commit specifications to implement"
    )
    current_index: int = Field(default=0, description="Index of the next commit to process")


class DispatcherOutput(BaseModel):
    """Output from the dispatcher agent."""

    current_task: CurrentTask = Field(description="The assembled task for the kernel to execute")
    current_index: int = Field(description="Updated index after dispatching")
    has_more_commits: bool = Field(description="Whether there are remaining commits to process")
