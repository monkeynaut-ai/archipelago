"""Designer callables — prompt_builder and instructions_provider.

Both take DesignerInput so templating can inline per-run state.
Instructions are loaded from the bundled template file and resolved
via archetype.templating.resolve.
"""

from __future__ import annotations

from pathlib import Path

from archetype.templating import resolve

from archipelago.agents.designer.models import DesignerInput
from archipelago.models import DesignDocument, FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def designer_prompt_builder(state: DesignerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Follow your instructions to produce the design document."
    )


def designer_instructions_provider(state: DesignerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        FeatureDefinition=FeatureDefinition,
        DesignDocument=DesignDocument,
    )
