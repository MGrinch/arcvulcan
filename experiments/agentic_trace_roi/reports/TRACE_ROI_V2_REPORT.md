# Trace ROI V2 Report

Generated: deterministic fixture run

## Inputs used

- Trace fixtures: 2
- Emitted spans: 14
- Outcomes: {"failure": 1, "success": 1}

## Standards-first contract

This pass emits span-like JSONL aligned with the local OpenInference-compatible
contract in `standards/openinference_trace_contract.md`. It does not create
a new production tracing standard and does not require external services.

## Pattern candidates found

| Pattern | Success count | Failure count | Unknown count |
| --- | ---: | ---: | ---: |
| hypothesis_labeled_commands | 1 | 0 | 0 |
| no_repeated_failed_commands | 1 | 0 | 0 |
| read_before_patch | 1 | 0 | 0 |
| verifier_after_patch | 1 | 0 | 0 |

## Success-vs-failure deltas

- Repeated failed command surplus: 1
- Positive patterns in this tiny fixture set are trace-quality signals only.
- This is not an A/B improvement result.

## A/B measurement table

| Gate | Baseline | Candidate | Result |
| --- | --- | --- | --- |
| Trace fixture ingestion | none | standards-first fixture adapter | passed on tiny fixtures |
| Ready-made tooling readiness | custom-first | span-compatible export first | ready for Phoenix/Promptfoo smoke |
| Agent improvement | unmeasured | unmeasured | not claimed |

## Accepted rules

No behavioral rule is accepted yet. Pass 1 only proves trace shape and local
fixture processing.

## Abandoned rules with rationale

No rule abandoned yet. A rule should be abandoned when a local A/B fails to move
pass rate, command count, token estimate, wrong-file edits, or verifier evidence.

## Next highest-ROI implementation

Try a ready-made trace/eval smoke before writing custom mining code:

1. Phoenix or another OpenTelemetry/OpenInference-compatible local trace viewer.
2. Promptfoo-style trace assertions for coding-agent behavior.
3. Custom diagnostic miner only for signal not covered by the ready-made path.
