"""Single-source builders for ``extra_env`` and ``extra_volumes`` passed
to ``run_process``.

Coordinates contributions from individual env-var-driven helpers
(``_proxy_config``, ``_git_config``, …) so call sites only need to
invoke two functions regardless of how many env-var-driven inputs
exist.
"""

from archipelago.systems._git_config import build_git_env
from archipelago.systems._proxy_config import build_proxy_env, build_proxy_volumes


def build_extra_env() -> dict[str, str] | None:
    """Merge every env-var contribution into a single dict.

    Returns ``None`` when nothing contributes, matching the contract
    ``run_process`` expects for "no extras."
    """
    combined: dict[str, str] = {}
    proxy = build_proxy_env()
    if proxy:
        combined.update(proxy)
    git = build_git_env()
    if git:
        combined.update(git)
    return combined or None


def build_extra_volumes() -> dict[str, dict[str, str]] | None:
    """Aggregate every bind-mount contribution into a single dict.

    Today only the proxy CA mount contributes; this exists as a
    coordinator so adding future mount sources doesn't touch call sites.
    """
    combined: dict[str, dict[str, str]] = {}
    proxy = build_proxy_volumes()
    if proxy:
        combined.update(proxy)
    return combined or None
