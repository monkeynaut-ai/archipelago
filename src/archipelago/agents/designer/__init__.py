"""Designer agent — Cluster A in the Phase 2 tensions analysis.

Reads a FeatureDefinition + target codebase and produces a DesignDocument.
"""

from __future__ import annotations

from archipelago.agents.designer.primitive import designer
from archipelago.agents.models import DesignerInput, DesignerOutput

__all__ = [
    "DesignerInput",
    "DesignerOutput",
    "designer",
]
