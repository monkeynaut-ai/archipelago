"""Public API surface for archipelago.models."""

from __future__ import annotations

import archipelago.models as models_pkg


class TestPublicAPI:
    def test_given_archipelago_models_when_imported_then_all_matches_expected(self):
        assert set(models_pkg.__all__) == {
            "AcceptanceCriteria",
            "Assumptions",
            "BusinessOutcomes",
            "ChangeSetRef",
            "ChangeSetsDocument",
            "ChangeSetsDocumentFrontmatter",
            "CodebaseSource",
            "Constraints",
            "Dependencies",
            "DesignDocument",
            "DesignDocumentFrontmatter",
            "DesiredOutcomes",
            "FeatureDefinition",
            "FeatureDefinitionFrontmatter",
            "ScopeBoundaries",
            "Task",
            "TDDPlan",
            "TDDPlanFrontmatter",
            "UserOutcomes",
            "slugify",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in models_pkg.__all__:
            assert hasattr(models_pkg, name), f"{name} listed in __all__ but missing"
