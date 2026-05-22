"""Build env + bind-mount arguments for routing agent traffic through a proxy.

Reads two env vars:
  ARCHIPELAGO_PROXY_URL       e.g. http://host.docker.internal:8080
  ARCHIPELAGO_PROXY_CA_PATH   host path to a CA cert in PEM format

Both must be set to enable proxy routing. If only one is set, logs a
warning and treats the wiring as disabled.

Two exposed functions:
  * ``build_proxy_env`` — env vars routing HTTPS through the proxy and
    pointing Node at the mitmproxy CA inside the container.
  * ``build_proxy_volumes`` — bind mount of the CA into the container.
"""

import logging
import os

logger = logging.getLogger(__name__)

_CONTAINER_CA_PATH = "/etc/archipelago/mitmproxy-ca.crt"


def _read_proxy_env() -> tuple[str, str] | None:
    """Return (url, ca_path) if both env vars are set, else None.

    Logs a warning when exactly one is set (partial config ignored).
    """
    url = os.environ.get("ARCHIPELAGO_PROXY_URL", "").strip()
    ca_path = os.environ.get("ARCHIPELAGO_PROXY_CA_PATH", "").strip()
    if not url and not ca_path:
        return None
    if not (url and ca_path):
        logger.warning(
            "proxy wiring needs both ARCHIPELAGO_PROXY_URL and ARCHIPELAGO_PROXY_CA_PATH; "
            "got url=%r ca_path=%r — ignoring",
            url,
            ca_path,
        )
        return None
    return url, ca_path


def build_proxy_env() -> dict[str, str] | None:
    config = _read_proxy_env()
    if config is None:
        return None
    url, _ca_path = config
    return {
        "HTTPS_PROXY": url,
        "NODE_EXTRA_CA_CERTS": _CONTAINER_CA_PATH,
    }


def build_proxy_volumes() -> dict[str, dict[str, str]] | None:
    config = _read_proxy_env()
    if config is None:
        return None
    _url, ca_path = config
    return {ca_path: {"bind": _CONTAINER_CA_PATH, "mode": "ro"}}
