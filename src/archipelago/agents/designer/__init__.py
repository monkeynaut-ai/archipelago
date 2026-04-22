"""Designer agent — Cluster A in the Phase 2 tensions analysis.

Reads a FeatureDefinition + target codebase and produces a DesignDocument.
"""

from __future__ import annotations

from archipelago.agents.designer.models import (
    DesignerInput,
    DesignerOutput,
)
from archipelago.agents.designer.primitive import designer

__all__ = [
    "DesignerInput",
    "DesignerOutput",
    "designer",
]
