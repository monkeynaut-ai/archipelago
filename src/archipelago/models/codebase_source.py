"""CodebaseSource — identifies a target codebase by repo URL + ref.

Ambient credentials (SSH agent / environment token) provide auth for v1;
no auth field on the model.
"""

from __future__ import annotations

from pydantic import BaseModel


class CodebaseSource(BaseModel):
    """A repo URL + a ref (commit SHA, branch, or tag)."""

    repo_url: str
    ref: str
