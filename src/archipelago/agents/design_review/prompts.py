"""Instruction + prompt builders for the two design reviewers.

Correctness traces the design against the feature definition (positive
specs: acceptance criteria, interfaces; negative specs: scope boundaries,
constraints). Quality judges the design against engineering rubrics using
the Designer-captured investigation summary as codebase context.
"""

from __future__ import annotations

from archetype.markdown import render_instance

from archipelago.models.design_review import DesignReviewerInput

_CORRECTNESS_INSTRUCTIONS = """\
You review a software design document for CORRECTNESS against a feature \
definition. Score each dimension MEETS_BAR, NEEDS_IMPROVEMENT, or INADEQUATE:

- requirement_coverage: every acceptance criterion is addressed by the design.
- interface_fidelity: declared interfaces match what the feature requires.
- scope_discipline: the design stays within the feature's scope boundaries.
- constraint_adherence: the design honors every stated constraint.

Any dimension you score INADEQUATE MUST have at least one must_fix finding \
citing that dimension. Put concrete, enumerated reasoning in reviewer_notes; \
a score without reasoning is meaningless.
"""

_QUALITY_INSTRUCTIONS = """\
You review a software design document for ENGINEERING QUALITY. Score each \
dimension MEETS_BAR, NEEDS_IMPROVEMENT, or INADEQUATE:

- cohesion: each unit has one clear responsibility.
- modularity: clean boundaries, low coupling between units.
- abstraction_quality: abstractions are at the right level, not leaky.

Use the supplied investigation summary as the codebase context the design \
was made against. Any dimension you score INADEQUATE MUST have at least one \
must_fix finding citing that dimension. Put concrete reasoning in reviewer_notes.
"""


def correctness_instructions(_state: DesignReviewerInput) -> str:
    return _CORRECTNESS_INSTRUCTIONS


def correctness_prompt(state: DesignReviewerInput) -> str:
    return (
        "# Feature Definition\n\n"
        f"{render_instance(state.feature_definition)}\n\n"
        "# Design Document\n\n"
        f"{render_instance(state.design_document)}\n"
    )


def quality_instructions(_state: DesignReviewerInput) -> str:
    return _QUALITY_INSTRUCTIONS


def quality_prompt(state: DesignReviewerInput) -> str:
    return (
        "# Design Document\n\n"
        f"{render_instance(state.design_document)}\n\n"
        "# Investigation Summary (codebase context)\n\n"
        "```\n"
        f"{state.investigation_summary_text}\n"
        "```\n"
    )
