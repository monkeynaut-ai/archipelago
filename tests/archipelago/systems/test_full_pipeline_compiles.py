from __future__ import annotations

from agent_foundry.compiler.primitive_compiler import compile_runtime_plan
from agent_foundry.primitives.plan import PrimitivePlan

from archipelago.systems.pipeline import full_pipeline


def test_full_pipeline_compiles() -> None:
    compile_runtime_plan(PrimitivePlan(root=full_pipeline))
