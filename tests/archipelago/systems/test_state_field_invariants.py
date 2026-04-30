"""Subset-invariant tests for design_pipeline and full_pipeline.

For every step in every Sequence, the step's input model's *required*
fields must be reachable from the accumulated state at that step's
position (the Sequence's own input union the outputs of preceding
steps). Same rule for every Loop's `loop_in`.

agent-foundry's `_validate_sequence` already enforces this at compose
time and raises `TypeMismatchError` if it fails. These tests pin the
same invariants explicitly per position, so:

- A future reader can see the exact accumulated-state shape at every
  boundary without running the validator.
- The pipeline still has a regression net if the upstream validator's
  semantics change.
- Topology refactors (adding/removing steps, changing input/output
  models) surface as test failures in this file rather than as
  late-stage runtime errors.

The Loop body Sequences are checked recursively the same way.
"""

from __future__ import annotations

from agent_foundry.primitives.models import Loop, Sequence, get_type_args
from agent_foundry.primitives.plan import PrimitivePlan
from pydantic import BaseModel

from archipelago.systems.design_pipeline import design_pipeline
from archipelago.systems.pipeline import full_pipeline


def _required_fields(model: type[BaseModel]) -> set[str]:
    """Names of fields the model REQUIRES (no default, not optional-with-None)."""
    return {name for name, info in model.model_fields.items() if info.is_required()}


def _all_fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields.keys())


def _assert_required_reachable(
    input_type: type[BaseModel],
    available: set[str],
    position: str,
) -> None:
    missing = _required_fields(input_type) - available
    assert not missing, (
        f"{position}: {input_type.__name__} requires fields {sorted(missing)} "
        f"not reachable from accumulated state {sorted(available)}"
    )


class TestDesignPipelineInvariants:
    """design_pipeline = Sequence[DesignPipelineState, DesignPipelineState](
        steps=[workspace_bootstrap, designer]
    )"""

    def test_plan_validates_without_error(self):
        # Smoke: compose-time validator runs the full subset check.
        # If this passes, every per-position assertion below is implied.
        PrimitivePlan(root=design_pipeline).validate()

    def test_step_0_workspace_bootstrap_inputs_reachable(self):
        seq_in, _ = get_type_args(design_pipeline)
        step = design_pipeline.steps[0]
        step_in, _ = get_type_args(step)
        accumulated = _all_fields(seq_in)
        _assert_required_reachable(step_in, accumulated, "design_pipeline.steps[0] input")

    def test_step_1_designer_inputs_reachable(self):
        seq_in, _ = get_type_args(design_pipeline)
        step0 = design_pipeline.steps[0]
        _, step0_out = get_type_args(step0)
        step1 = design_pipeline.steps[1]
        step1_in, _ = get_type_args(step1)
        accumulated = _all_fields(seq_in) | _all_fields(step0_out)
        _assert_required_reachable(step1_in, accumulated, "design_pipeline.steps[1] input")


class TestFullPipelineInvariants:
    """full_pipeline = Sequence[FullPipelineState, FullPipelineState](
        steps=[
            workspace_bootstrap,
            designer,
            change_set_planner,
            Loop[ChangeSetsLoopState, ChangeSetsLoopState](
                over=_change_sets_over,
                item_key="current_change_set",
                body=Sequence[ChangeSetProcessingState, ChangeSetProcessingState](
                    steps=[
                        prepare_change_set_workspace,
                        log_change_set_name,
                        tdd_planner,
                        Loop[StepsLoopState, StepsLoopState](
                            over=_steps_over,
                            item_key="current_step",
                            body=Sequence[StepProcessingState, StepProcessingState](
                                steps=[log_change_set_step_name],
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )"""

    def test_plan_validates_without_error(self):
        # Smoke: validates the entire nested topology.
        PrimitivePlan(root=full_pipeline).validate()

    def test_top_level_step_inputs_reachable(self):
        seq_in, _ = get_type_args(full_pipeline)
        accumulated = _all_fields(seq_in)
        for i, step in enumerate(full_pipeline.steps):
            step_in, step_out = get_type_args(step)
            _assert_required_reachable(step_in, accumulated, f"full_pipeline.steps[{i}] input")
            accumulated |= _all_fields(step_out)

    def test_outer_loop_loop_in_reachable(self):
        # The outer Loop sits at index 3. Accumulated state at that
        # position is FullPipelineState plus the outputs of steps 0-2.
        seq_in, _ = get_type_args(full_pipeline)
        accumulated = _all_fields(seq_in)
        for i in range(3):
            _, step_out = get_type_args(full_pipeline.steps[i])
            accumulated |= _all_fields(step_out)

        outer_loop = full_pipeline.steps[3]
        assert isinstance(outer_loop, Loop)
        loop_in, _ = get_type_args(outer_loop)
        _assert_required_reachable(loop_in, accumulated, "full_pipeline outer Loop input (loop_in)")

    def test_outer_body_step_inputs_reachable(self):
        outer_loop = full_pipeline.steps[3]
        assert isinstance(outer_loop, Loop)
        body = outer_loop.body
        assert isinstance(body, Sequence)
        body_in, _ = get_type_args(body)

        # Accumulated state at body entry: body's declared input + the
        # Loop's item_key (set by Loop just before invoking the body).
        # ChangeSetProcessingState declares current_change_set so this
        # is a tautology, but we model it explicitly for clarity.
        accumulated = _all_fields(body_in) | {outer_loop.item_key}
        for i, step in enumerate(body.steps):
            step_in, step_out = get_type_args(step)
            _assert_required_reachable(
                step_in, accumulated, f"full_pipeline outer body steps[{i}] input"
            )
            accumulated |= _all_fields(step_out)

    def test_inner_loop_loop_in_reachable(self):
        outer_loop = full_pipeline.steps[3]
        assert isinstance(outer_loop, Loop)
        outer_body = outer_loop.body
        assert isinstance(outer_body, Sequence)
        # Inner loop is the last step in the outer body.
        inner_loop = outer_body.steps[-1]
        assert isinstance(inner_loop, Loop)

        outer_body_in, _ = get_type_args(outer_body)
        accumulated = _all_fields(outer_body_in) | {outer_loop.item_key}
        for step in outer_body.steps[:-1]:
            _, step_out = get_type_args(step)
            accumulated |= _all_fields(step_out)

        inner_loop_in, _ = get_type_args(inner_loop)
        _assert_required_reachable(
            inner_loop_in, accumulated, "full_pipeline inner Loop input (loop_in)"
        )

    def test_inner_body_step_inputs_reachable(self):
        outer_loop = full_pipeline.steps[3]
        assert isinstance(outer_loop, Loop)
        outer_body = outer_loop.body
        assert isinstance(outer_body, Sequence)
        inner_loop = outer_body.steps[-1]
        assert isinstance(inner_loop, Loop)
        inner_body = inner_loop.body
        assert isinstance(inner_body, Sequence)

        inner_body_in, _ = get_type_args(inner_body)
        accumulated = _all_fields(inner_body_in) | {inner_loop.item_key}
        for i, step in enumerate(inner_body.steps):
            step_in, step_out = get_type_args(step)
            _assert_required_reachable(
                step_in, accumulated, f"full_pipeline inner body steps[{i}] input"
            )
            accumulated |= _all_fields(step_out)
