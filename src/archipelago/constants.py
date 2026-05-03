"""Archipelago workspace constants.

Directory layout
----------------
WORKSPACE_ROOT           /workspace
WORKSPACE_CODEBASE_PATH  /workspace/codebase
WORKSPACE_DOCUMENTS_PATH /workspace/documents

GID map (controls write access to each zone)
--------------------------------------------
GID_DOCUMENTS = 1001  WORKSPACE_DOCUMENTS_PATH (and all subdirs)
GID_CODEBASE  = 1002  WORKSPACE_CODEBASE_PATH  (excluding tests/)
GID_TESTS     = 1003  WORKSPACE_CODEBASE_PATH/tests
"""

from __future__ import annotations

# --- Directory names ---
WORKSPACE_ROOT: str = "/workspace"
CODEBASE_DIR_NAME: str = "codebase"
DOCUMENTS_DIR_NAME: str = "documents"

# --- Composed paths ---
WORKSPACE_CODEBASE_PATH: str = f"{WORKSPACE_ROOT}/{CODEBASE_DIR_NAME}"
WORKSPACE_DOCUMENTS_PATH: str = f"{WORKSPACE_ROOT}/{DOCUMENTS_DIR_NAME}"

# --- GIDs ---
GID_DOCUMENTS: int = 1001
GID_CODEBASE: int = 1002
GID_TESTS: int = 1003
