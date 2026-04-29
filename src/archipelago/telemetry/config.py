import os

from agent_foundry.mlflow_adapter import MLFLOW_TRANSLATIONS
from agent_foundry.mlflow_adapter import enable as enable_mlflow_adapter
from agent_foundry.telemetry import RunDefinition, TelemetryConfig
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

MLFLOW_BASE_URL = os.environ.get("AF_MLFLOW_BASE_URL", "http://localhost:5000")
MLFLOW_EXPERIMENT_ID = os.environ.get("AF_MLFLOW_EXPERIMENT_ID", "0")

print("MFLOW_BASE_URL ", MLFLOW_BASE_URL)
print("MLFLOW_EXPERIMENT_ID", MLFLOW_EXPERIMENT_ID)


def _telemetry_configuration() -> TelemetryConfig:
    return TelemetryConfig(
        otlp_endpoint=f"{MLFLOW_BASE_URL}/v1/traces",
        otlp_headers={"x-mlflow-experiment-id": MLFLOW_EXPERIMENT_ID},
        service_name="archipelago",
        attribute_translations=MLFLOW_TRANSLATIONS,
        run_definition=RunDefinition(
            name=lambda inp: f"feature-{inp.feature_name}",
            params=lambda inp: {
                "feature": inp.feature_name,
                "kind": inp.target,
                "qty": inp.quantity,
            },
            tags={"product": "archipelago", "env": "local"},
            metrics=lambda out, stats: (
                {"duration_ms": stats.duration_ms, "out_exists": 1}
                if out is not None
                else {"duration_ms": stats.duration_ms, "out_exists": 0}
            ),
        ),
    )


telemetry_configuration = _telemetry_configuration()


class MLflowInput(BaseModel):
    feature_name: str
    target: str
    quantity: int


input_model = MLflowInput(feature_name="All aboard", target="Crazy Train", quantity=7)


def attach_mlflow_adapter(event) -> None:
    enable_mlflow_adapter(
        config=telemetry_configuration,
        run_context=event.run_context,
        input_model=input_model,
        tracking_uri=MLFLOW_BASE_URL,
        experiment_id=MLFLOW_EXPERIMENT_ID,
    )
