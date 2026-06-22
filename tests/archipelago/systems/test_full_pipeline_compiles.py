from __future__ import annotations

from agent_foundry.compiler.compiler import compile_process
from agent_foundry.constructs import Process

from archipelago.systems.pipeline import full_pipeline


def test_full_pipeline_compiles() -> None:
    compile_process(Process(root=full_pipeline))
