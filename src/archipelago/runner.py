"""Archipelago pipeline runner."""

import json
from pathlib import Path
from typing import Any

from agent_foundry.compiler.compiler import run_plan
from agent_foundry.planner.wiring_plan import GraphWiringPlan
from agent_foundry.registry.registry import RoleRegistry

from archipelago.agents.unit_test_writer import UnitTestWriter
from archipelago.models import CurrentTask

PLAN_PATH = Path(__file__).parent / "archipelago_system.json"


def load_archipelago_plan() -> GraphWiringPlan:
    """Load the static Archipelago pipeline plan."""
    plan_data = json.loads(PLAN_PATH.read_text())
    return GraphWiringPlan(**plan_data)


def run_archipelago(
    job_specification: dict[str, Any],
    registry: RoleRegistry | None = None,
    plan: GraphWiringPlan | None = None,
) -> dict[str, Any]:
    """Run the Archipelago pipeline end-to-end.

    Args:
        job_specification: Parsed job definition dict with objective, constraints, and commits.
        registry: Optional role registry (auto-loaded if None).
        plan: Optional plan (auto-loaded if None).

    Returns:
        The final state dict with all pipeline artifacts.
    """
    if registry is None:
        registry = RoleRegistry.with_product_specs(Path(__file__).parent / "roles")

    if plan is None:
        plan = load_archipelago_plan()

    initial_state = {"job_specification": job_specification}
    return run_plan(plan, registry, initial_state=initial_state)


def run_dev_test(dev_test_input: dict[str, Any]) -> dict[str, Any]:
    """Bypass the full pipeline and run only a single worker directly."""
    task = CurrentTask(
        objective=dev_test_input.get("objective", ""),
        title=dev_test_input.get("commit_spec", {}).get("title", ""),
        acceptance_criteria=dev_test_input.get("commit_spec", {}).get("acceptance_criteria", []),
        test_focus=dev_test_input.get("commit_spec", {}).get("test_focus", ""),
        implementation_focus=dev_test_input.get("commit_spec", {}).get("implementation_focus", ""),
        repo_url=dev_test_input.get("repo_url"),
        repo_ref=dev_test_input.get("repo_ref", "main"),
    )
    node_config = dev_test_input.get("node_config", {})
    agent = UnitTestWriter(
        prompt_preamble=node_config.get("prompt_preamble"),
        role_instructions_path=node_config.get("role_instructions_path"),
        acp_readonly_dirs=node_config.get("acp_readonly_dirs"),
        acp_hidden_dirs=node_config.get("acp_hidden_dirs"),
    )
    result = agent(current_task=task)
    return result.model_dump()
