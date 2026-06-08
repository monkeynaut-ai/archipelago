"""Shared pytest fixtures for archipelago tests."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the archipelago repo root.

    Resolves relative to this file: conftest.py → tests/archipelago → tests
    → repo root. That's two parents up.
    """
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def minimal_feature_definition():
    """A fully-populated FeatureDefinition for tests that need one.

    Imported lazily so this module can be imported before Slice 2 body
    tasks land (during Task 2.1, archipelago.models doesn't exist yet).
    Tests that use this fixture implicitly depend on Task 2.4 having
    landed.
    """
    from archipelago.models import (
        AcceptanceCriteria,
        Assumptions,
        BusinessOutcomes,
        Constraints,
        Dependencies,
        DesiredOutcomes,
        FeatureDefinition,
        FeatureDefinitionFrontmatter,
        ScopeBoundaries,
        UserOutcomes,
    )

    return FeatureDefinition(
        frontmatter=FeatureDefinitionFrontmatter(
            feature_slug="demo",
            created_at="2026-04-21",
        ),
        heading="Demo Feature",
        problem_statement="A gap exists.",
        feature_intent="Close the gap.",
        desired_outcomes=DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u1"]),
            business_outcomes=BusinessOutcomes(items=["b1"]),
        ),
        scope_boundaries=ScopeBoundaries(items=["not-X"]),
        assumptions=Assumptions(items=["a1"]),
        dependencies=Dependencies(items=["d1"]),
        constraints=Constraints(items=["c1"]),
        acceptance_criteria=AcceptanceCriteria(items=["ac1"]),
    )


@pytest.fixture(scope="session")
def archipelago_volume_registry() -> set[str]:
    """Session-scoped set of workspace-volume names that integration tests
    have created. Tests register names via `archipelago_volume_registry.add(...)`
    after creating a volume; the session finalizer removes exactly those
    names (not all `archipelago-ws-*` volumes on the host — a blanket sweep
    would destroy a developer's manually-created inspection volumes).
    """
    return set()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_registered_volumes(archipelago_volume_registry):
    """Session-end cleanup: remove volumes that tests explicitly registered.
    No-op when Docker isn't reachable."""
    yield
    if not archipelago_volume_registry:
        return
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        return
    for name in archipelago_volume_registry:
        with contextlib.suppress(Exception):
            client.volumes.get(name).remove(force=True)
