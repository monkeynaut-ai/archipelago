"""Public API surface for archipelago.systems."""

from __future__ import annotations

import archipelago.systems as systems_pkg


class TestPublicAPI:
    def test_given_systems_package_when_imported_then_all_matches_expected(self):
        assert set(systems_pkg.__all__) == {
            "BASE_IMAGE_TAG",
            "ChangeSetProcessingState",
            "ChangeSetsLoopState",
            "FullPipelineState",
            "TaskProcessingState",
            "TDDPlanLoopState",
            "full_pipeline",
            "generate_volume_name",
            "run_full_pipeline",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in systems_pkg.__all__:
            assert hasattr(systems_pkg, name)
