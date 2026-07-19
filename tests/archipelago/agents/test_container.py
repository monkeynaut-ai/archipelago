"""Tests for the shared agent container configuration."""

from __future__ import annotations

import pytest
from agent_foundry.agents import NetworkMode

from archipelago.agents._container import agent_container_config


class TestAgentContainerConfig:
    def test_given_memory_limit_when_built_then_limit_applied(self):
        config = agent_container_config(mem_limit_mb=3072)

        assert config.mem_limit_mb == 3072

    def test_given_default_when_built_then_egress_enabled(self):
        config = agent_container_config(mem_limit_mb=3072)

        assert config.network == NetworkMode.BRIDGE


AGENT_MODULES = [
    "archipelago.agents.designer.primitive",
    "archipelago.agents.change_set_planner.primitive",
    "archipelago.agents.tdd_planner.primitive",
    "archipelago.agents.tester.primitive",
    "archipelago.agents.implementer.primitive",
    "archipelago.agents.pr_creator.primitive",
]


class TestAgentsHaveEgress:
    @pytest.mark.parametrize("module_name", AGENT_MODULES)
    def test_given_agent_primitive_when_declared_then_container_has_egress(self, module_name):
        import importlib

        module = importlib.import_module(module_name)
        agents = [
            value
            for value in vars(module).values()
            if getattr(value, "container_config", None) is not None
        ]
        assert agents, f"no agent declaration found in {module_name}"

        for agent in agents:
            assert agent.container_config.network != NetworkMode.NONE
