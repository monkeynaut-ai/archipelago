"""Inspect a Claude Code stream.jsonl file without loading the whole thing.

Designer / agent runs produce stream.jsonl files that can be 100s of KB. This
utility offers tiered drilling into them so you can gauge agent fidelity
without eating your context budget:

  --summary          Counts + final-result summary (cost, tokens, duration).
  --text-only        Thinking + text blocks per logical turn, tools stripped.
  --turn N           One logical turn in full JSON (all events sharing its
                     message.id, plus trailing tool-result user events).
  --envelope         The agent's final outcome — the last StructuredOutput
                     input, or the ``result`` event's narrative if
                     StructuredOutput wasn't injected.
  --tool-calls NAMES Every tool_use block matching comma-separated names.

Usage:
    python scripts/inspect_stream.py --summary path/to/stream.jsonl
    python scripts/inspect_stream.py --text-only path/to/stream.jsonl > thinking.txt
    python scripts/inspect_stream.py --turn 5 path/to/stream.jsonl
    python scripts/inspect_stream.py --tool-calls Write,Edit path/to/stream.jsonl

Logical-turn note: Claude Code splits one agent turn across multiple JSONL
events (one per content block — thinking, text, tool_use). They share the
same ``message.id``; this script counts turns by unique id.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def _iter_events(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(f"warning: line {i} is not valid JSON: {exc}", file=sys.stderr)


def _assistant_content(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event.get("type") != "assistant":
        return []
    content = event.get("message", {}).get("content")
    return content if isinstance(content, list) else []


def _assistant_message_id(event: dict[str, Any]) -> str | None:
    if event.get("type") != "assistant":
        return None
    return event.get("message", {}).get("id")


def _print_counter(title: str, counter: Counter[str]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not counter:
        print("  (none)")
        return
    width = max(len(k) for k in counter)
    for name, count in counter.most_common():
        print(f"  {name:<{width}}  {count:>5}")


def mode_summary(path: Path) -> None:
    type_counter: Counter[str] = Counter()
    tool_counter: Counter[str] = Counter()
    stop_counter: Counter[str] = Counter()
    content_block_counter: Counter[str] = Counter()
    logical_turn_ids: set[str] = set()
    models: set[str] = set()
    result_event: dict[str, Any] | None = None

    for event in _iter_events(path):
        type_counter[event.get("type", "<none>")] += 1

        if event.get("type") == "assistant":
            msg_id = _assistant_message_id(event)
            if msg_id:
                logical_turn_ids.add(msg_id)
            msg = event.get("message", {})
            if reason := msg.get("stop_reason"):
                stop_counter[reason] += 1
            if model := msg.get("model"):
                models.add(model)
            for block in _assistant_content(event):
                block_type = block.get("type", "<unknown>")
                content_block_counter[block_type] += 1
                if block_type == "tool_use":
                    tool_counter[block.get("name", "<unnamed>")] += 1
        elif event.get("type") == "result":
            result_event = event

    print(f"File:              {path}")
    print(f"Size on disk:      {path.stat().st_size:,} bytes")
    print(f"Logical turns:     {len(logical_turn_ids)}")
    if models:
        print(f"Model(s):          {', '.join(sorted(models))}")

    if result_event is not None:
        duration_ms = result_event.get("duration_ms")
        if duration_ms:
            print(f"Duration:          {duration_ms / 1000:.1f}s")
        if (num_turns := result_event.get("num_turns")) is not None:
            print(f"Run's num_turns:   {num_turns}")
        if (cost := result_event.get("total_cost_usd")) is not None:
            print(f"Total cost:        ${cost:.4f}")
        usage = result_event.get("usage") or {}
        if usage:
            print("Token usage:")
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            ):
                if key in usage:
                    print(f"  {key:<32} {usage[key]:>10,}")
        if (is_error := result_event.get("is_error")) is not None:
            print(f"is_error:          {is_error}")
        if (subtype := result_event.get("subtype")) is not None:
            print(f"result.subtype:    {subtype}")

    _print_counter("Event types", type_counter)
    _print_counter("Assistant content blocks", content_block_counter)
    _print_counter("Tool calls", tool_counter)
    _print_counter("Stop reasons", stop_counter)


def mode_text_only(path: Path) -> None:
    """Thinking + text blocks per logical turn, no tool payloads."""
    current_id: str | None = None
    turn_number = 0
    buffered_blocks: list[tuple[str, str]] = []

    def _flush() -> None:
        if not buffered_blocks:
            return
        print(f"\n=== turn {turn_number} ({current_id}) ===")
        for kind, text in buffered_blocks:
            prefix = "[thinking]" if kind == "thinking" else "[text]"
            print(f"\n{prefix}")
            print(text)
        buffered_blocks.clear()

    for event in _iter_events(path):
        msg_id = _assistant_message_id(event)
        if msg_id is None:
            continue
        if msg_id != current_id:
            _flush()
            current_id = msg_id
            turn_number += 1
        for block in _assistant_content(event):
            kind = block.get("type")
            if kind == "thinking":
                buffered_blocks.append((kind, block.get("thinking", "")))
            elif kind == "text":
                buffered_blocks.append((kind, block.get("text", "")))
    _flush()


def mode_turn(path: Path, turn_number: int) -> None:
    """Emit full JSON for the Nth logical turn and its trailing tool-result events."""
    seen_ids: list[str] = []
    capturing = False
    target_id: str | None = None

    for event in _iter_events(path):
        event_type = event.get("type")
        msg_id = _assistant_message_id(event)

        if event_type == "assistant" and msg_id and msg_id not in seen_ids:
            seen_ids.append(msg_id)
            if capturing and msg_id != target_id:
                return  # reached the next logical turn
            if len(seen_ids) == turn_number:
                capturing = True
                target_id = msg_id

        if capturing:
            if event_type == "assistant" and msg_id != target_id:
                return
            print(json.dumps(event, indent=2))

    if not capturing:
        print(
            f"error: only {len(seen_ids)} logical turn(s) in file; cannot show turn {turn_number}",
            file=sys.stderr,
        )
        sys.exit(1)


def mode_envelope(path: Path) -> None:
    """Last StructuredOutput input, or the result-event narrative if absent."""
    last_structured: dict[str, Any] | None = None
    result_event: dict[str, Any] | None = None

    for event in _iter_events(path):
        if event.get("type") == "result":
            result_event = event
        for block in _assistant_content(event):
            if block.get("type") == "tool_use" and block.get("name") == "StructuredOutput":
                last_structured = block.get("input")

    if last_structured is not None:
        print("# Source: StructuredOutput tool call")
        print(json.dumps(last_structured, indent=2))
        return

    if result_event is not None:
        print("# Source: result event (StructuredOutput was not called)")
        narrative = result_event.get("result")
        if narrative:
            print(narrative)
        else:
            print(json.dumps(result_event, indent=2))
        return

    print("error: no StructuredOutput call and no result event found", file=sys.stderr)
    sys.exit(1)


def mode_tool_calls(path: Path, tool_names: list[str]) -> None:
    wanted = set(tool_names)
    turn_ids: list[str] = []
    for event in _iter_events(path):
        msg_id = _assistant_message_id(event)
        if msg_id and msg_id not in turn_ids:
            turn_ids.append(msg_id)
        for block in _assistant_content(event):
            if block.get("type") == "tool_use" and block.get("name") in wanted:
                turn_number = turn_ids.index(msg_id) + 1 if msg_id in turn_ids else -1
                print(f"\n=== turn {turn_number}: {block.get('name')} (id {block.get('id')}) ===")
                print(json.dumps(block.get("input"), indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_stream",
        description="Inspect a Claude Code stream.jsonl without loading it whole.",
    )
    parser.add_argument("path", type=Path, help="Path to stream.jsonl")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--text-only", action="store_true")
    mode.add_argument("--turn", type=int, metavar="N")
    mode.add_argument("--envelope", action="store_true")
    mode.add_argument("--tool-calls", metavar="NAMES", help="Comma-separated tool names")

    args = parser.parse_args(argv)
    if not args.path.exists():
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2

    if args.summary:
        mode_summary(args.path)
    elif args.text_only:
        mode_text_only(args.path)
    elif args.turn is not None:
        mode_turn(args.path, args.turn)
    elif args.envelope:
        mode_envelope(args.path)
    elif args.tool_calls:
        mode_tool_calls(args.path, [s.strip() for s in args.tool_calls.split(",") if s.strip()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
