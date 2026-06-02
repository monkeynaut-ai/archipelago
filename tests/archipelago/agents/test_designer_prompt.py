from __future__ import annotations

import pytest

from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.agents.designer.primitive import designer_prompt_builder
from archipelago.agents.models import DesignerInput
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle.model_construct(volume_name="v", root="/workspace")


def _input(**kw) -> DesignerInput:
    base = dict(
        workspace_handle=_handle(),
        feature_definition=None,  # prompt builder does not read it
    )
    base.update(kw)
    return DesignerInput.model_construct(**base)


def _failing_verdict() -> DesignReviewVerdict:
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    scores[CorrectnessDimension.REQUIREMENT_COVERAGE] = DimensionScore.INADEQUATE
    correctness = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="AC-2 missing",
                suggested_resolution="add AC-2 handling",
                dimension=CorrectnessDimension.REQUIREMENT_COVERAGE,
            )
        ],
        reviewer_notes="n",
    )
    quality = QualityVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in QualityDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )
    return DesignReviewVerdict(
        correctness=correctness, quality=quality, passed=False, attempt_number=1
    )


def test_first_pass_prompt_has_no_revision_language() -> None:
    prompt = designer_prompt_builder(_input(design_review_verdict=None))
    assert "/workspace" in prompt
    assert "revise" not in prompt.lower()


def test_revision_prompt_references_prior_design_and_findings() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
        )
    )
    assert "/workspace/documents/design.md" in prompt
    assert "AC-2 missing" in prompt
    assert "revise" in prompt.lower()


def test_revision_without_path_raises() -> None:
    with pytest.raises(AssertionError):
        designer_prompt_builder(
            _input(design_review_verdict=_failing_verdict(), design_document_path=None)
        )


def test_revision_prompt_includes_operator_guidance() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
            operator_guidance="Use an event queue instead of polling.",
        )
    )
    assert "Use an event queue instead of polling." in prompt
    assert "operator" in prompt.lower()


def test_revision_prompt_omits_guidance_section_when_absent() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
        )
    )
    assert "operator guidance" not in prompt.lower()
