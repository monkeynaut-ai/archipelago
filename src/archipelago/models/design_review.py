"""Design-review boundary types: categorical verdicts from the two
in-process reviewers and the aggregated verdict the Retry loop gates on.

The reviewer AICalls return the wrapper output models (one verdict field
each) so their shared internal field names don't collide when Agent
Foundry merges AICall output flat into pipeline state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from archipelago.models.design_document import DesignDocument
from archipelago.models.feature_definition import FeatureDefinition


class DimensionScore(StrEnum):
    MEETS_BAR = "meets_bar"
    NEEDS_IMPROVEMENT = "needs_improvement"
    INADEQUATE = "inadequate"


class CorrectnessDimension(StrEnum):
    REQUIREMENT_COVERAGE = "requirement_coverage"
    INTERFACE_FIDELITY = "interface_fidelity"
    SCOPE_DISCIPLINE = "scope_discipline"
    CONSTRAINT_ADHERENCE = "constraint_adherence"


class QualityDimension(StrEnum):
    COHESION = "cohesion"
    MODULARITY = "modularity"
    ABSTRACTION_QUALITY = "abstraction_quality"


class CorrectnessMustFixFinding(BaseModel):
    description: str
    suggested_resolution: str
    dimension: CorrectnessDimension


class QualityMustFixFinding(BaseModel):
    description: str
    suggested_resolution: str
    dimension: QualityDimension


class CorrectnessVerdict(BaseModel):
    dimension_scores: dict[CorrectnessDimension, DimensionScore]
    must_fix_findings: list[CorrectnessMustFixFinding]
    reviewer_notes: str

    @model_validator(mode="after")
    def _all_dimensions_scored(self) -> Self:
        missing = set(CorrectnessDimension) - set(self.dimension_scores)
        if missing:
            raise ValueError(
                f"Every CorrectnessDimension must be scored. "
                f"Missing: {sorted(d.value for d in missing)}"
            )
        return self

    @model_validator(mode="after")
    def _inadequate_dims_have_findings(self) -> Self:
        inadequate = {d for d, s in self.dimension_scores.items() if s == DimensionScore.INADEQUATE}
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: {sorted(d.value for d in missing)}"
            )
        return self


class QualityVerdict(BaseModel):
    dimension_scores: dict[QualityDimension, DimensionScore]
    must_fix_findings: list[QualityMustFixFinding]
    reviewer_notes: str

    @model_validator(mode="after")
    def _all_dimensions_scored(self) -> Self:
        missing = set(QualityDimension) - set(self.dimension_scores)
        if missing:
            raise ValueError(
                f"Every QualityDimension must be scored. "
                f"Missing: {sorted(d.value for d in missing)}"
            )
        return self

    @model_validator(mode="after")
    def _inadequate_dims_have_findings(self) -> Self:
        inadequate = {d for d, s in self.dimension_scores.items() if s == DimensionScore.INADEQUATE}
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: {sorted(d.value for d in missing)}"
            )
        return self


class CorrectnessReviewOutput(BaseModel):
    correctness_verdict: CorrectnessVerdict


class QualityReviewOutput(BaseModel):
    quality_verdict: QualityVerdict


class DesignReviewVerdict(BaseModel):
    correctness: CorrectnessVerdict
    quality: QualityVerdict
    passed: bool
    attempt_number: int


class DesignReviewerInput(BaseModel):
    """Projected slice the reviewer AICalls read from loop state.

    Correctness reads feature_definition + design_document; quality reads
    design_document + investigation_summary_text. Both reviewers share this
    input type and the compiler projects the fields each prompt builder uses.
    """

    feature_definition: FeatureDefinition
    design_document: DesignDocument
    investigation_summary_text: str
