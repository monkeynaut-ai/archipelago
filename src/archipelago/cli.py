"""Archipelago pipeline CLI."""

import argparse
import logging
import os
import sys
from pathlib import Path

import structlog
import yaml
from dotenv import load_dotenv

from archipelago.runner import run_archipelago, run_dev_test


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog with JSON output for production, readable output for development."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(),
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Archipelago pipeline")
    parser.add_argument("-f", "--file", required=True, help="Path to YAML input file")
    args = parser.parse_args(argv)

    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        data = yaml.safe_load(input_path.read_text())
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("Error: YAML must be a mapping", file=sys.stderr)
        return 1

    if "dev_test_input" in data:
        result = run_dev_test(data["dev_test_input"])
        print(yaml.dump(result, default_flow_style=False))
        return 0

    if "job_specification" not in data:
        print(
            "Error: YAML must contain 'job_specification' or 'dev_test_input' key",
            file=sys.stderr,
        )
        return 1

    result = run_archipelago(data["job_specification"])
    print(yaml.dump(result, default_flow_style=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
