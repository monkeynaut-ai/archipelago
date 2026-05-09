from __future__ import annotations

# --- Directory names ---
WORKSPACE_ROOT: str = "/workspace"
CODEBASE_DIR_NAME: str = "codebase"
DOCUMENTS_DIR_NAME: str = "documents"

# --- Composed paths ---
WORKSPACE_CODEBASE_PATH: str = f"{WORKSPACE_ROOT}/{CODEBASE_DIR_NAME}"
WORKSPACE_DOCUMENTS_PATH: str = f"{WORKSPACE_ROOT}/{DOCUMENTS_DIR_NAME}"

# --- Well-known filenames / subdirectory names ---
CHANGE_SETS_DIR_NAME: str = "change-sets"
FEATURE_DEFINITION_FILENAME: str = "feature_definition.md"
LESSONS_LEARNED_FILENAME: str = "lessons-learned.md"

# --- GIDs ---
GID_DOCUMENTS: int = 1001
GID_CODEBASE: int = 1002
GID_TESTS: int = 1003
