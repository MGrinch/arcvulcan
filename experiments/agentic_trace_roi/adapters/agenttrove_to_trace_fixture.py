#!/usr/bin/env python3
"""Convert a bounded local AgentTrove-style JSONL sample into trace fixtures.

This adapter does not download AgentTrove. It only reads a local sample file so
large dataset use remains explicit and reviewable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_LIMIT = 20


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object row")
            yield row


def coerce_messages(row: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("messages", "conversations", "trajectory", "turns"):
        value = row.get(key)
        if isinstance(value, list):
            messages = []
            for item in value:
                if isinstance(item, dict):
                    messages.append(
                        {
                            "role": item.get("role") or item.get("from") or item.get("speaker") or "unknown",
                            "content": item.get("content") or item.get("value") or item.get("text") or "",
                        }
                    )
                else:
                    messages.append({"role": "unknown", "content": str(item)})
            return messages
    text = row.get("text") or row.get("prompt") or row.get("input") or ""
    return [{"role": "unknown", "content": str(text)}] if text else []


def coerce_outcome(row: dict[str, Any]) -> tuple[str, float | int | None]:
    reward = row.get("reward")
    if isinstance(reward, (int, float)):
        if reward > 0:
            return "success", reward
        if reward < 0:
            return "failure", reward
        return "unknown", reward

    for key in ("outcome", "label", "result"):
        value = str(row.get(key, "")).lower()
        if value in {"success", "passed", "pass", "solved"}:
            return "success", reward
        if value in {"failure", "failed", "fail", "unsolved"}:
            return "failure", reward
    return "unknown", reward if isinstance(reward, (int, float)) else None


def normalize_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    outcome, reward = coerce_outcome(row)
    source_id = row.get("id") or row.get("trace_id") or row.get("source_id") or f"agenttrove-sample-{index:04d}"
    return {
        "trace_id": str(source_id),
        "source": "agenttrove",
        "task_family": "unknown",
        "messages": coerce_messages(row),
        "tool_calls": row.get("tool_calls") if isinstance(row.get("tool_calls"), list) else [],
        "commands": row.get("commands") if isinstance(row.get("commands"), list) else [],
        "observations": row.get("observations") if isinstance(row.get("observations"), list) else [],
        "outcome": outcome,
        "reward": reward,
        "tags": ["agenttrove_local_sample"],
        "metadata": {
            "source_dataset": row.get("source") or row.get("dataset") or "AgentTrove local sample",
            "source_license": row.get("license") or "check upstream sample metadata",
            "adapter_note": "Bounded local sample conversion; no download performed.",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local AgentTrove-style JSONL sample.")
    parser.add_argument("--output", required=True, help="Output trace fixture JSONL.")
    parser.add_argument("--sample-size", type=int, required=True, help="Maximum rows to convert.")
    parser.add_argument("--allow-large-sample", action="store_true", help="Allow sample size above 20.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size < 1:
        raise SystemExit("--sample-size must be positive")
    if args.sample_size > DEFAULT_LIMIT and not args.allow_large_sample:
        raise SystemExit("sample size above 20 requires --allow-large-sample")

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converted = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, row in enumerate(read_jsonl(input_path), start=1):
            if converted >= args.sample_size:
                break
            handle.write(json.dumps(normalize_row(row, index), sort_keys=True, separators=(",", ":")) + "\n")
            converted += 1

    print(json.dumps({"converted": converted, "output": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

