"""Full end-to-end test: bootstrap → designer → design.md.

Marked `integration`; skipped when Docker, network, or claude-code
authentication is unavailable. Phase 2's completion criterion.

Running requires:
- Docker daemon reachable.
- GH_TOKEN or GITHUB_TOKEN in env (for cloning the private pinned repo).
- ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in env (for the designer).
- agent-worker:latest image available locally.

    GH_TOKEN=$(gh auth token) ANTHROPIC_API_KEY=... \\
        pdm test-integration tests/archipelago/systems/test_design_pipeline_integration.py
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

import docker
import pytest
from archetype.markdown import validate_markdown

from archipelago.models import CodebaseSource, DesignDocument, FeatureDefinition
from archipelago.systems.design_pipeline import run_design_pipeline

pytestmark = pytest.mark.integration

REPO_URL = "https://github.com/730alchemy/agent-foundry.git"
REF = "main"


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _claude_auth_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


@pytest.fixture
def docker_and_auth_client():
    if not _docker_available():
        pytest.skip("Docker daemon not reachable")
    if not _claude_auth_available():
        pytest.skip("ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN not set")
    return docker.from_env()


@pytest.fixture
def cleanup_volumes(docker_and_auth_client, archipelago_volume_registry):
    created: list[str] = []
    try:
        yield created
    finally:
        for name in created:
            archipelago_volume_registry.add(name)
            with contextlib.suppress(Exception):
                docker_and_auth_client.volumes.get(name).remove(force=True)


class TestDesignPipelineEndToEnd:
    @pytest.mark.asyncio
    @pytest.mark.timeout(1800)
    async def test_given_run_observability_when_pipeline_then_design_document_produced(
        self, docker_and_auth_client, cleanup_volumes, repo_root: Path
    ):
        feature_text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        feature = validate_markdown(feature_text, FeatureDefinition)
        source = CodebaseSource(repo_url=REPO_URL, ref=REF)

        final = await run_design_pipeline(
            feature_definition=feature,
            codebase_source=source,
        )
        assert final.workspace_handle is not None
        cleanup_volumes.append(final.workspace_handle.volume_name)
        assert final.designer_output is not None

        # Read the produced design.md out of the volume.
        design_text = docker_and_auth_client.containers.run(
            "alpine:3.20",
            command=["cat", final.designer_output.design_document],
            volumes={final.workspace_handle.volume_name: {"bind": "/workspace", "mode": "ro"}},
            remove=True,
        ).decode("utf-8", errors="replace")

        # Parseable as a DesignDocument.
        design = validate_markdown(design_text, DesignDocument)

        # Every section has non-trivial content.
        MIN_CHARS = 40
        for name, value in [
            ("summary", design.summary),
            ("current_state_context", design.current_state_context),
            ("components", design.components),
            ("architecture", design.architecture),
            ("acceptance_criteria", design.acceptance_criteria),
            ("test_strategy", design.test_strategy),
            ("risks_and_open_items", design.risks_and_open_items),
            ("resolved_assumptions", design.resolved_assumptions),
        ]:
            assert len(value.strip()) >= MIN_CHARS, (
                f"section {name!r} too short: {len(value)} chars"
            )

        assert "Run Observability" in design_text
