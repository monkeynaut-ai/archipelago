"""Build env + bind-mount arguments for routing agent traffic through a proxy.

Reads two env vars:
  ARCHIPELAGO_PROXY_URL       e.g. http://host.docker.internal:8080
  ARCHIPELAGO_PROXY_CA_PATH   host path to a CA cert in PEM format

If both are set, returns wiring that:
  * routes the agent's HTTPS through the proxy (HTTPS_PROXY env in the container)
  * mounts the CA at /etc/archipelago/mitmproxy-ca.crt (read-only)
  * tells Node to trust that CA (NODE_EXTRA_CA_CERTS env in the container)

If neither is set, returns (None, None). If only one is set, logs a warning
and returns (None, None) — partial config is silently ignored.
"""

import logging
import os

logger = logging.getLogger(__name__)

_CONTAINER_CA_PATH = "/etc/archipelago/mitmproxy-ca.crt"


def build_proxy_wiring() -> tuple[dict[str, str] | None, dict[str, dict[str, str]] | None]:
    url = os.environ.get("ARCHIPELAGO_PROXY_URL", "").strip()
    ca_path = os.environ.get("ARCHIPELAGO_PROXY_CA_PATH", "").strip()
    if not url and not ca_path:
        return None, None
    if not (url and ca_path):
        logger.warning(
            "proxy wiring needs both ARCHIPELAGO_PROXY_URL and ARCHIPELAGO_PROXY_CA_PATH; "
            "got url=%r ca_path=%r — ignoring",
            url,
            ca_path,
        )
        return None, None
    extra_env = {
        "HTTPS_PROXY": url,
        "NODE_EXTRA_CA_CERTS": _CONTAINER_CA_PATH,
    }
    extra_volumes = {ca_path: {"bind": _CONTAINER_CA_PATH, "mode": "ro"}}
    return extra_env, extra_volumes
