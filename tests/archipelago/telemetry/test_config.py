"""Tests for the MLflow run-input binding."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from archipelago.models.codebase_source import CodebaseSource
from archipelago.telemetry.config import (
    ArchipelagoRunInput,
    build_run_input,
    run_name,
    run_params,
)


@pytest.fixture
def source() -> CodebaseSource:
    return CodebaseSource(repo_url="https://github.com/acme/widget.git", ref="main")


class TestBuildRunInput:
    def test_given_feature_and_source_when_built_then_carries_real_values(
        self, minimal_feature_definition, source
    ):
        run_input = build_run_input(minimal_feature_definition, source)

        assert run_input.feature_name == "Demo Feature"
        assert run_input.repo_url == "https://github.com/acme/widget.git"
        assert run_input.ref == "main"


class TestRunNameAndParams:
    def test_given_run_input_when_named_then_uses_feature_name(self):
        run_input = ArchipelagoRunInput(
            feature_name="Demo Feature",
            repo_url="https://github.com/acme/widget.git",
            ref="main",
        )

        assert run_name(run_input) == "feature-Demo Feature"

    def test_given_run_input_when_params_read_then_all_fields_logged(self):
        run_input = ArchipelagoRunInput(
            feature_name="Demo Feature",
            repo_url="https://github.com/acme/widget.git",
            ref="abc1234",
        )

        assert run_params(run_input) == {
            "feature": "Demo Feature",
            "repo": "https://github.com/acme/widget.git",
            "ref": "abc1234",
        }

    def test_given_foreign_model_when_named_then_type_error(self):
        class Other(BaseModel):
            feature_name: str

        with pytest.raises(TypeError):
            run_name(Other(feature_name="nope"))
