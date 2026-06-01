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
from archipelago.models.current_task_document import (
    ChangeSetContext,
    CurrentTaskDocument,
    CurrentTaskFrontmatter,
)
from archipelago.models.design_document import (
    DesignDocument,
    DesignDocumentFrontmatter,
)
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessReviewOutput,
    CorrectnessVerdict,
    DesignReviewerInput,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityMustFixFinding,
    QualityReviewOutput,
    QualityVerdict,
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
from archipelago.models.tdd_plan import (
    Task,
    TDDPlan,
    TDDPlanFrontmatter,
)

__all__ = [
    "AcceptanceCriteria",
    "Assumptions",
    "BusinessOutcomes",
    "ChangeSetContext",
    "ChangeSetRef",
    "ChangeSetsDocument",
    "ChangeSetsDocumentFrontmatter",
    "CodebaseSource",
    "Constraints",
    "CorrectnessDimension",
    "CorrectnessMustFixFinding",
    "CorrectnessReviewOutput",
    "CorrectnessVerdict",
    "CurrentTaskDocument",
    "CurrentTaskFrontmatter",
    "Dependencies",
    "DesignDocument",
    "DesignDocumentFrontmatter",
    "DesignReviewVerdict",
    "DesignReviewerInput",
    "DesiredOutcomes",
    "DimensionScore",
    "FeatureDefinition",
    "FeatureDefinitionFrontmatter",
    "QualityDimension",
    "QualityMustFixFinding",
    "QualityReviewOutput",
    "QualityVerdict",
    "ScopeBoundaries",
    "TDDPlan",
    "TDDPlanFrontmatter",
    "Task",
    "UserOutcomes",
    "slugify",
]
