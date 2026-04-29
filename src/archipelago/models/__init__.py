"""Archipelago domain models — FeatureDefinition, DesignDocument, and
supporting types. Every boundary type in this package is a Pydantic
BaseModel subclass.
"""

from __future__ import annotations

from archipelago.models.change_sets_document import (
    ChangeSetRef,
    ChangeSetsDocument,
    ChangeSetsDocumentFrontmatter,
    slugify,
)
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
from archipelago.models.steps_document import (
    StepRef,
    StepsDocument,
    StepsDocumentFrontmatter,
)

__all__ = [
    "AcceptanceCriteria",
    "Assumptions",
    "BusinessOutcomes",
    "ChangeSetRef",
    "ChangeSetsDocument",
    "ChangeSetsDocumentFrontmatter",
    "CodebaseSource",
    "Constraints",
    "Dependencies",
    "DesignDocument",
    "DesignDocumentFrontmatter",
    "DesiredOutcomes",
    "FeatureDefinition",
    "FeatureDefinitionFrontmatter",
    "ScopeBoundaries",
    "StepRef",
    "StepsDocument",
    "StepsDocumentFrontmatter",
    "UserOutcomes",
    "slugify",
]
