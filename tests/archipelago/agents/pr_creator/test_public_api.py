"""Public API surface for archipelago.agents.pr_creator and archipelago.agents."""

from __future__ import annotations

import archipelago.agents as agents_pkg
import archipelago.agents.pr_creator as pr_creator_pkg


class TestPrCreatorPackageAPI:
    def test_given_pr_creator_package_when_imported_then_all_matches_expected(self):
        assert set(pr_creator_pkg.__all__) == {
            "pr_creator",
            "PrCreatorInput",
            "PrCreatorOutput",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in pr_creator_pkg.__all__:
            assert hasattr(pr_creator_pkg, name)


class TestAgentsPackageAPI:
    def test_given_agents_package_when_imported_then_pr_creator_reachable(self):
        assert "pr_creator" in agents_pkg.__all__
        assert hasattr(agents_pkg, "pr_creator")
