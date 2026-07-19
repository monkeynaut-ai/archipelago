"""Shared container configuration for Archipelago's agents."""

from __future__ import annotations

from agent_foundry.agents import ContainerConfig, NetworkMode


def agent_container_config(*, mem_limit_mb: int) -> ContainerConfig:
    """Container config for an agent that needs outbound network access.

    Egress is opt-in and every Archipelago agent needs it: each one drives an
    LLM over the network, and the implementer and PR creator also reach GitHub.
    Declaring it here keeps the grant in one auditable place.
    """
    return ContainerConfig(mem_limit_mb=mem_limit_mb, network=NetworkMode.BRIDGE)
