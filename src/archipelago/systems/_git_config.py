"""Forward git identity env vars to agent containers

If ``GIT_USER_NAME`` and/or ``GIT_USER_EMAIL`` are set in the host environment,
include them in ``extra_env`` so the worker container can access them.
"""

import os


def build_git_env() -> dict[str, str]:
    env: dict[str, str] = {}
    name = os.environ.get("GIT_USER_NAME", "").strip()
    email = os.environ.get("GIT_USER_EMAIL", "").strip()
    if name:
        env["GIT_USER_NAME"] = name
    if email:
        env["GIT_USER_EMAIL"] = email
    return env
