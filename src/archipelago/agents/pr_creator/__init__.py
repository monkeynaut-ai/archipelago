"""PR Creator agent — final step in the full pipeline.

Pushes the feature branch and opens a GitHub pull request using the
feature definition and design document as source material for the description.
"""

from __future__ import annotations

from archipelago.agents.models import PrCreatorInput, PrCreatorOutput
from archipelago.agents.pr_creator.primitive import pr_creator

__all__ = [
    "PrCreatorInput",
    "PrCreatorOutput",
    "pr_creator",
]
