"""The two design-review AICalls.

Plain AICalls on the default invoke path — no custom executor. v1 has no
transient-failure translation (Divergence #3): any inference error propagates
and aborts the pipeline, the same loud-failure stance as on_exhaustion. This
also keeps the anthropic SDK out of archipelago — there is nothing here to
catch provider exceptions, so there is no reason to import them.
"""

from __future__ import annotations

from agent_foundry.ai_models.inference import InferenceParameters
from agent_foundry.primitives.ai_call import AICall, ModelInput

from archipelago.agents.design_review.prompts import (
    correctness_instructions,
    correctness_prompt,
    quality_instructions,
    quality_prompt,
)
from archipelago.config import DESIGN_REVIEW_MODEL
from archipelago.models.design_review import (
    CorrectnessReviewOutput,
    DesignReviewInput,
    QualityReviewOutput,
)

_REVIEW_PARAMETERS = InferenceParameters(temperature=0.0, max_tokens=8_000)


design_correctness_review = AICall[DesignReviewInput, CorrectnessReviewOutput](
    name="design_correctness_review",
    model_input=ModelInput[DesignReviewInput](
        instructions=correctness_instructions,
        prompt=correctness_prompt,
    ),
    model=DESIGN_REVIEW_MODEL,
    parameters=_REVIEW_PARAMETERS,
    timeout_seconds=120,
)

design_quality_review = AICall[DesignReviewInput, QualityReviewOutput](
    name="design_quality_review",
    model_input=ModelInput[DesignReviewInput](
        instructions=quality_instructions,
        prompt=quality_prompt,
    ),
    model=DESIGN_REVIEW_MODEL,
    parameters=_REVIEW_PARAMETERS,
    timeout_seconds=120,
)
