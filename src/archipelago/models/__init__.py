"""Archipelago domain models — FeatureDefinition, DesignDocument, and
supporting types. Every boundary type in this package is a Pydantic
BaseModel subclass.
"""

from __future__ import annotations

from archipelago.models.codebase_source import CodebaseSource
from archipelago.models.design_document import (
    DesignDocument,
    DesignDocumentFrontmatter,
)
from archipelago.models.feature_definition import (
    AcceptanceCriteria,
    Assumptions,
    BusinessOutcomes,
    Constraints,
    Dependencies,
    DesiredOutcomes,
    FeatureDefinition,
    FeatureDefinitionFrontmatter,
    ScopeBoundaries,
    UserOutcomes,
)

__all__ = [
    "AcceptanceCriteria",
    "Assumptions",
    "BusinessOutcomes",
    "CodebaseSource",
    "Constraints",
    "Dependencies",
    "DesignDocument",
    "DesignDocumentFrontmatter",
    "DesiredOutcomes",
    "FeatureDefinition",
    "FeatureDefinitionFrontmatter",
    "ScopeBoundaries",
    "UserOutcomes",
]
