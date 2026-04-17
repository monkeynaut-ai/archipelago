"""Container lifecycle manager for Archipelago Docker workers.

Re-exports Agent Container container infrastructure with Archipelago-specific defaults.
"""

from agent_foundry.agents.lifecycle import (
    DEFAULT_ENV_ALLOWLIST as _ACP_ENV_ALLOWLIST,
)
from agent_foundry.agents.lifecycle import (  # noqa: F401
    ContainerConfig,
    ContainerHandle,
    ContainerManager,
)

# Archipelago extends the generic Agent Container allowlist with product-specific env vars
DEFAULT_ENV_ALLOWLIST = _ACP_ENV_ALLOWLIST | {
    "ARCHIPELAGO_WS_URL",
    "GITHUB_TOKEN",
    "GIT_USER_NAME",
    "GIT_USER_EMAIL",
}


def create_archipelago_container_manager(client, **kwargs) -> ContainerManager:
    """Factory that creates a ContainerManager with Archipelago defaults."""
    return ContainerManager(
        client,
        default_image=kwargs.get("default_image", "agent-worker:latest"),
        env_allowlist=kwargs.get("env_allowlist", DEFAULT_ENV_ALLOWLIST),
    )
