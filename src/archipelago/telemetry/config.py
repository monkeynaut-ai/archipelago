"""MLflow telemetry configuration and the per-run adapter hook.

The hook is built as a factory because the run's input is not reachable from
``RunStartingEvent`` — the pipeline knows the feature and codebase at the
``run_process`` call site and binds them into the closure here.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from agent_foundry.mlflow_adapter import MLFLOW_TRANSLATIONS
from agent_foundry.mlflow_adapter import enable as enable_mlflow_adapter
from agent_foundry.telemetry import RunDefinition, TelemetryConfig
from dotenv import load_dotenv
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_foundry.orchestration import RunStartingEvent

    from archipelago.models import CodebaseSource, FeatureDefinition

load_dotenv()

MLFLOW_BASE_URL = os.environ.get("AF_MLFLOW_BASE_URL", "http://localhost:5000")
MLFLOW_EXPERIMENT_ID = os.environ.get("AF_MLFLOW_EXPERIMENT_ID", "0")


class ArchipelagoRunInput(BaseModel):
    """What a run is logged against in MLflow: which feature, which codebase."""

    feature_name: str
    repo_url: str
    ref: str


def build_run_input(
    feature_definition: FeatureDefinition, codebase_source: CodebaseSource
) -> ArchipelagoRunInput:
    return ArchipelagoRunInput(
        feature_name=feature_definition.heading,
        repo_url=codebase_source.repo_url,
        ref=codebase_source.ref,
    )


def _as_run_input(inp: BaseModel) -> ArchipelagoRunInput:
    """Narrow the framework's ``BaseModel`` callable contract to the input model
    this configuration declares. Raises if a different model arrives."""
    if type(inp) is not ArchipelagoRunInput:
        raise TypeError(f"expected ArchipelagoRunInput, got {type(inp).__name__}")
    return inp


def run_name(inp: BaseModel) -> str:
    return f"feature-{_as_run_input(inp).feature_name}"


def run_params(inp: BaseModel) -> dict[str, Any]:
    run_input = _as_run_input(inp)
    return {
        "feature": run_input.feature_name,
        "repo": run_input.repo_url,
        "ref": run_input.ref,
    }


def _telemetry_configuration() -> TelemetryConfig:
    return TelemetryConfig(
        otlp_endpoint=f"{MLFLOW_BASE_URL}/v1/traces",
        otlp_headers={"x-mlflow-experiment-id": MLFLOW_EXPERIMENT_ID},
        service_name="archipelago",
        attribute_translations=MLFLOW_TRANSLATIONS,
        run_definition=RunDefinition(
            name=run_name,
            params=run_params,
            tags={"product": "archipelago", "env": "local"},
            metrics=lambda out, stats: (
                {"duration_ms": stats.duration_ms, "out_exists": 1}
                if out is not None
                else {"duration_ms": stats.duration_ms, "out_exists": 0}
            ),
        ),
    )


telemetry_configuration = _telemetry_configuration()


def make_mlflow_hook(
    feature_definition: FeatureDefinition, codebase_source: CodebaseSource
) -> Callable[[RunStartingEvent], None]:
    run_input = build_run_input(feature_definition, codebase_source)

    def attach_mlflow_adapter(event: RunStartingEvent) -> None:
        enable_mlflow_adapter(
            config=telemetry_configuration,
            run_context=event.run_context,
            input_model=run_input,
            tracking_uri=MLFLOW_BASE_URL,
            experiment_id=MLFLOW_EXPERIMENT_ID,
        )

    return attach_mlflow_adapter
