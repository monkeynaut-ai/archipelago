"""Per-agent output models for the Archipelago pipeline.

Each model defines the typed return value of a single agent. Field names
map directly to LangGraph state keys — the connector calls ``model_dump()``
to produce the dict that LangGraph merges into state.
"""

from pydantic import BaseModel, Field

from archipelago.models import AgentWorkerResult
from archipelago.types import CommitHash, WorkSpace


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
