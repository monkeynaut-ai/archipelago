"""Designer AgentAction declaration.

Container config per design §6.1:
- /workspace visible (codebase read-only + documents writable via chmod).
- Only /workspace/documents/ writable.
- REUSE_NEW_SESSION reuse policy.
- 30-minute timeout (declaration only — not enforced by the
  orchestrator in Phase 2; Designer can run longer in practice).
"""

from __future__ import annotations

from pathlib import Path

from agent_foundry.constructs import AgentAction, ContainerReusePolicy
from agent_foundry.orchestration import run_agent_in_container
from archetype.templating import resolve

from archipelago.agents._container import agent_container_config
from archipelago.agents.models import DesignerInput, DesignerOutput
from archipelago.config import DESIGNER_EFFORT, DESIGNER_MODEL
from archipelago.constants import GID_DOCUMENTS
from archipelago.models import DesignDocument, FeatureDefinition
from archipelago.models.design_review import DimensionScore

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def designer_prompt_builder(state: DesignerInput) -> str:
    if state.design_review_verdict is None:
        return (
            f"The workspace is mounted at {state.workspace_handle.root}. "
            f"Follow your instructions to produce the design document."
        )

    verdict = state.design_review_verdict
    assert state.design_document_path is not None, (
        "design_document_path must be set on a revision pass (a verdict implies "
        "a prior Designer run wrote the design)."
    )
    findings = [*verdict.correctness.must_fix_findings, *verdict.quality.must_fix_findings]
    findings_text = "\n".join(
        f"- [{f.dimension.value}] {f.description} — {f.suggested_resolution}" for f in findings
    )
    inadequate = [
        d.value
        for scores in (verdict.correctness.dimension_scores, verdict.quality.dimension_scores)
        for d, s in scores.items()
        if s == DimensionScore.INADEQUATE
    ]
    guidance_section = ""
    if state.operator_guidance is not None:
        guidance_section = (
            f"\n\nAn operator reviewed the failed attempts and provided this "
            f"guidance — treat it as the top priority:\n{state.operator_guidance}"
        )
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Your prior design at {state.design_document_path} did not pass review "
        f"(attempt {verdict.attempt_number}). Read it, then revise it in place to "
        f"resolve the following must-fix findings:\n\n{findings_text}\n\n"
        f"Dimensions scored INADEQUATE: {', '.join(inadequate)}. "
        f"Write the revised design document to the same path."
        f"{guidance_section}"
    )


def designer_instructions_provider(state: DesignerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        FeatureDefinition=FeatureDefinition,
        DesignDocument=DesignDocument,
    )


designer = AgentAction[DesignerInput, DesignerOutput](
    name="designer",
    prompt_builder=designer_prompt_builder,
    instructions_provider=designer_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]  # agent-foundry's executor returns BaseModel; the AgentFilePath marker narrows at runtime.
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
    model=DESIGNER_MODEL,
    effort=DESIGNER_EFFORT,
    container_config=agent_container_config(mem_limit_mb=3072),
    cwd="/workspace/codebase",
)
