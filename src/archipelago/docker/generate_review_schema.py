"""Generate the CodeReview JSON schema from the Pydantic model and inject it
into CLAUDE-software-review.md."""

import json
import re
from pathlib import Path

from archipelago.models import CodeReview

REVIEW_MD_PATH = Path(__file__).parent / "CLAUDE-software-review.md"
SCHEMA_MARKER_START = "<!-- GENERATED_SCHEMA_START -->"
SCHEMA_MARKER_END = "<!-- GENERATED_SCHEMA_END -->"


def generate() -> None:
    schema = json.dumps(CodeReview.model_json_schema(), indent=2)

    content = REVIEW_MD_PATH.read_text()
    pattern = re.compile(
        re.escape(SCHEMA_MARKER_START) + r".*?" + re.escape(SCHEMA_MARKER_END),
        re.DOTALL,
    )
    replacement = f"{SCHEMA_MARKER_START}\n\n```json\n{schema}\n```\n\n{SCHEMA_MARKER_END}"

    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
    else:
        raise ValueError(
            f"Could not find schema markers in {REVIEW_MD_PATH}. "
            f"Ensure the file contains {SCHEMA_MARKER_START} and {SCHEMA_MARKER_END}."
        )

    REVIEW_MD_PATH.write_text(new_content)
    print(f"Schema injected into {REVIEW_MD_PATH}")


if __name__ == "__main__":
    generate()
