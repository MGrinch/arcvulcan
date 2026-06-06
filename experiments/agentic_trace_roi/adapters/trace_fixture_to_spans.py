#!/usr/bin/env python3
"""Convert local trace fixtures into span-like JSONL and a small ROI report.

The output is intentionally OpenTelemetry/OpenInference-compatible in shape,
but uses only the Python standard library so pass 1 has no dependency burden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = {
    "trace_id",
    "source",
    "task_family",
    "messages",
    "tool_calls",
    "commands",
    "observations",
    "outcome",
    "reward",
    "tags",
}


def stable_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


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


def validate_trace(trace: dict[str, Any], source_path: Path) -> None:
    missing = sorted(REQUIRED_FIELDS - set(trace))
    if missing:
        raise ValueError(f"{source_path}: trace {trace.get('trace_id', '<missing>')} missing {missing}")
    for field in ("messages", "tool_calls", "commands", "observations", "tags"):
        if not isinstance(trace[field], list):
            raise ValueError(f"{source_path}: trace {trace['trace_id']} field {field} must be a list")
    if trace["outcome"] not in {"success", "failure", "unknown"}:
        raise ValueError(f"{source_path}: trace {trace['trace_id']} has invalid outcome {trace['outcome']!r}")


def base_attributes(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace.source": trace["source"],
        "trace.task_family": trace["task_family"],
        "trace.outcome": trace["outcome"],
        "trace.tags": trace["tags"],
    }


def make_span(
    trace: dict[str, Any],
    family: str,
    name: str,
    index: int,
    parent_span_id: str | None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    span_id = stable_id(trace["trace_id"], family, name, index)
    merged = base_attributes(trace)
    merged["span.family"] = family
    if attributes:
        merged.update(attributes)
    return {
        "trace_id": trace["trace_id"],
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": name,
        "span_kind": family,
        "attributes": merged,
    }


def trace_to_spans(trace: dict[str, Any]) -> list[dict[str, Any]]:
    root = make_span(
        trace=trace,
        family="agent.run",
        name=f"agent.run {trace['trace_id']}",
        index=0,
        parent_span_id=None,
        attributes={
            "trace.reward": trace.get("reward"),
            "trace.message_count": len(trace["messages"]),
            "trace.command_count": len(trace["commands"]),
            "trace.tool_call_count": len(trace["tool_calls"]),
        },
    )
    spans = [root]
    root_id = root["span_id"]

    for index, message in enumerate(trace["messages"]):
        spans.append(
            make_span(
                trace,
                "agent.message",
                f"message.{message.get('role', 'unknown')}",
                index,
                root_id,
                {
                    "message.role": message.get("role", "unknown"),
                    "message.content_preview": str(message.get("content", ""))[:240],
                },
            )
        )

    for index, tool_call in enumerate(trace["tool_calls"]):
        spans.append(
            make_span(
                trace,
                "agent.tool_call",
                f"tool.{tool_call.get('name', 'unknown')}",
                index,
                root_id,
                {
                    "tool.name": tool_call.get("name", "unknown"),
                    "tool.status": tool_call.get("status", "unknown"),
                },
            )
        )

    for index, command in enumerate(trace["commands"]):
        family = "agent.verifier" if command.get("kind") == "verify" else "agent.command"
        attrs = {
            "command.text": command.get("command", ""),
            "command.kind": command.get("kind", "unknown"),
            "command.exit_code": command.get("exit_code"),
            "command.hypothesis": command.get("hypothesis", ""),
            "command.expected_observation": command.get("expected_observation", ""),
            "command.observed": command.get("observed", ""),
        }
        if family == "agent.verifier":
            attrs["verifier.name"] = command.get("command", "")
            attrs["verifier.exit_code"] = command.get("exit_code")
            attrs["verifier.passed"] = command.get("exit_code") == 0
        spans.append(make_span(trace, family, command.get("command", "command"), index, root_id, attrs))

    for index, observation in enumerate(trace["observations"]):
        spans.append(
            make_span(
                trace,
                "agent.artifact",
                f"observation.{observation.get('type', 'unknown')}",
                index,
                root_id,
                {
                    "artifact.type": observation.get("type", "observation"),
                    "artifact.summary": observation.get("summary", ""),
                },
            )
        )

    return spans


def command_text(command: dict[str, Any]) -> str:
    return str(command.get("command", "")).strip()


def has_read_before_patch(commands: list[dict[str, Any]]) -> bool:
    first_read = next((idx for idx, item in enumerate(commands) if item.get("kind") == "read"), None)
    first_patch = next((idx for idx, item in enumerate(commands) if item.get("kind") == "patch"), None)
    return first_read is not None and first_patch is not None and first_read < first_patch


def has_verifier_after_patch(commands: list[dict[str, Any]]) -> bool:
    patch_indices = [idx for idx, item in enumerate(commands) if item.get("kind") == "patch"]
    verify_indices = [idx for idx, item in enumerate(commands) if item.get("kind") == "verify" and item.get("exit_code") == 0]
    return bool(patch_indices and verify_indices and max(verify_indices) > min(patch_indices))


def repeated_failed_commands(commands: list[dict[str, Any]]) -> int:
    failed = [command_text(item) for item in commands if item.get("exit_code") not in (None, 0)]
    counts = Counter(failed)
    return sum(count - 1 for count in counts.values() if count > 1)


def hypothesis_labeled_ratio(commands: list[dict[str, Any]]) -> float:
    if not commands:
        return 1.0
    labeled = [item for item in commands if item.get("hypothesis") and item.get("expected_observation")]
    return len(labeled) / len(commands)


def pattern_flags(trace: dict[str, Any]) -> dict[str, bool]:
    commands = trace["commands"]
    return {
        "read_before_patch": has_read_before_patch(commands),
        "verifier_after_patch": has_verifier_after_patch(commands),
        "no_repeated_failed_commands": repeated_failed_commands(commands) == 0,
        "hypothesis_labeled_commands": hypothesis_labeled_ratio(commands) >= 0.8,
    }


def build_report(traces: list[dict[str, Any]], spans: list[dict[str, Any]]) -> str:
    outcome_counts = Counter(trace["outcome"] for trace in traces)
    pattern_by_outcome: dict[str, Counter[str]] = defaultdict(Counter)
    repeated_failures = 0

    for trace in traces:
        flags = pattern_flags(trace)
        repeated_failures += repeated_failed_commands(trace["commands"])
        for pattern, present in flags.items():
            if present:
                pattern_by_outcome[pattern][trace["outcome"]] += 1

    pattern_rows = []
    for pattern in sorted({pattern for trace in traces for pattern in pattern_flags(trace)}):
        counts = pattern_by_outcome[pattern]
        pattern_rows.append(
            f"| {pattern} | {counts.get('success', 0)} | {counts.get('failure', 0)} | {counts.get('unknown', 0)} |"
        )

    return "\n".join(
        [
            "# Trace ROI V2 Report",
            "",
            "Generated: deterministic fixture run",
            "",
            "## Inputs used",
            "",
            f"- Trace fixtures: {len(traces)}",
            f"- Emitted spans: {len(spans)}",
            f"- Outcomes: {json.dumps(dict(outcome_counts), sort_keys=True)}",
            "",
            "## Standards-first contract",
            "",
            "This pass emits span-like JSONL aligned with the local OpenInference-compatible",
            "contract in `standards/openinference_trace_contract.md`. It does not create",
            "a new production tracing standard and does not require external services.",
            "",
            "## Pattern candidates found",
            "",
            "| Pattern | Success count | Failure count | Unknown count |",
            "| --- | ---: | ---: | ---: |",
            *pattern_rows,
            "",
            "## Success-vs-failure deltas",
            "",
            f"- Repeated failed command surplus: {repeated_failures}",
            "- Positive patterns in this tiny fixture set are trace-quality signals only.",
            "- This is not an A/B improvement result.",
            "",
            "## A/B measurement table",
            "",
            "| Gate | Baseline | Candidate | Result |",
            "| --- | --- | --- | --- |",
            "| Trace fixture ingestion | none | standards-first fixture adapter | passed on tiny fixtures |",
            "| Ready-made tooling readiness | custom-first | span-compatible export first | ready for Phoenix/Promptfoo smoke |",
            "| Agent improvement | unmeasured | unmeasured | not claimed |",
            "",
            "## Accepted rules",
            "",
            "No behavioral rule is accepted yet. Pass 1 only proves trace shape and local",
            "fixture processing.",
            "",
            "## Abandoned rules with rationale",
            "",
            "No rule abandoned yet. A rule should be abandoned when a local A/B fails to move",
            "pass rate, command count, token estimate, wrong-file edits, or verifier evidence.",
            "",
            "## Next highest-ROI implementation",
            "",
            "Try a ready-made trace/eval smoke before writing custom mining code:",
            "",
            "1. Phoenix or another OpenTelemetry/OpenInference-compatible local trace viewer.",
            "2. Promptfoo-style trace assertions for coding-agent behavior.",
            "3. Custom diagnostic miner only for signal not covered by the ready-made path.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="Trace fixture JSONL path. Repeatable.")
    parser.add_argument("--output-spans", required=True, help="Output span JSONL path.")
    parser.add_argument("--output-report", required=True, help="Output Markdown report path.")
    parser.add_argument("--max-traces", type=int, default=20, help="Safety cap for pass-1 fixture processing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_traces < 1:
        raise SystemExit("--max-traces must be positive")

    traces: list[dict[str, Any]] = []
    for input_name in args.input:
        path = Path(input_name)
        for trace in read_jsonl(path):
            validate_trace(trace, path)
            traces.append(trace)
            if len(traces) > args.max_traces:
                raise SystemExit(f"trace count exceeds safety cap: {args.max_traces}")

    spans = [span for trace in traces for span in trace_to_spans(trace)]

    span_path = Path(args.output_spans)
    report_path = Path(args.output_report)
    span_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with span_path.open("w", encoding="utf-8", newline="\n") as handle:
        for span in spans:
            handle.write(json.dumps(span, sort_keys=True, separators=(",", ":")) + "\n")

    report_path.write_text(build_report(traces, spans), encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "traces": len(traces),
                "spans": len(spans),
                "output_spans": str(span_path),
                "output_report": str(report_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
