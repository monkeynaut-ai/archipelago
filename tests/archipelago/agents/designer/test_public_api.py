"""Public API surface for archipelago.agents.designer and archipelago.agents."""

from __future__ import annotations

import archipelago.agents as agents_pkg
import archipelago.agents.designer as designer_pkg


class TestDesignerPackageAPI:
    def test_given_designer_package_when_imported_then_all_matches_expected(self):
        assert set(designer_pkg.__all__) == {
            "designer",
            "DesignerInput",
            "DesignerOutput",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in designer_pkg.__all__:
            assert hasattr(designer_pkg, name)


class TestAgentsPackageAPI:
    def test_given_agents_package_when_imported_then_designer_reachable(self):
        assert "designer" in agents_pkg.__all__
        assert hasattr(agents_pkg, "designer")
