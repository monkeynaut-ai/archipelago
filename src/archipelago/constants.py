"""Archipelago workspace GID constants.

Each GID controls write access to one workspace zone. Workspace setup
(workspace_ops) chowns each zone to root:<GID> mode 775 so only agents
holding that supplementary GID can write there; others get r-x (read-only).

GID map
-------
GID_DOCUMENTS = 1001  /workspace/documents (and all subdirs)
GID_CODEBASE  = 1002  /workspace/codebase  (excluding tests/)
GID_TESTS     = 1003  /workspace/codebase/tests
"""

from __future__ import annotations

GID_DOCUMENTS: int = 1001
GID_CODEBASE: int = 1002
GID_TESTS: int = 1003
