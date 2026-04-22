"""Archipelago domain models — FeatureDefinition, DesignDocument, and
supporting types. Every boundary type in this package is a Pydantic
BaseModel subclass.
"""

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
    "Constraints",
    "Dependencies",
    "DesiredOutcomes",
    "FeatureDefinition",
    "FeatureDefinitionFrontmatter",
    "ScopeBoundaries",
    "UserOutcomes",
]
