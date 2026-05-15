# Workflow Status

This repo is aligned to the unresolved backlog that matches the current integrated code snapshot.

- Audited UTC: 2026-03-21T02:11:50.8881211Z
- Active cycle: 1
- Implemented worker items already present: 111 / 149 (74.5%)
- Remaining active worker backlog: 38 / 149 (25.5%)
- Exact restart point: the next execution begins at worker round 1 on the canonical unresolved backlog in `workflow/queues/`.
- Compiler status: precompilers 16, 17 and final 18 are reset to round 1 and should wait for fresh worker packages from the unresolved backlog.

## Cold-Stop Position

- Window 01: 9/13 already done, 4 left. Next bug: BUG-27 - Invalid protocol paths silently downgrade to the fallback protocol
- Window 02: 8/11 already done, 3 left. Next bug: BUG-80 - Whitespace-only blank lines are not treated as paragraph breaks in grounding corpora, so poison and clean context can collapse into one oversized paragraph
- Window 03: 7/10 already done, 3 left. Next bug: BUG-70 - Hard no-overlap chunk splitting breaks retrieval at passage boundaries
- Window 04: 9/10 already done, 1 left. Next bug: BUG-09 - Session orchestration loses conversational continuity across turns
- Window 05: 10/10 already done, 0 left. Queue complete.
- Window 06: 8/12 already done, 4 left. Next bug: BUG-50 - Mirror enablement and privacy controls are not propagated or auditable across session tooling
- Window 07: 9/11 already done, 2 left. Next bug: BUG-90 - `repro_replay_diff.py` ignores cross-file `run.json.issue_id` drift in turn bundles
- Window 08: 6/8 already done, 2 left. Next bug: BUG-45 - `targeted_sweep.py` sanitizes child output before extracting run paths
- Window 09: 6/8 already done, 2 left. Next bug: BUG-113 - Repro smoke tools emit other tools' report names and schema versions, and `validate_schemas.py` blesses the mismatch as canonical
- Window 10: 3/5 already done, 2 left. Next bug: BUG-79 - `tools/artifact_roundtrip.py` ignores nested `child_runs/**/*.json` when given a run directory
- Window 11: 9/12 already done, 3 left. Next bug: BUG-42 - `grounding_injection_audit.py` is environment-sensitive and can misattribute failures
- Window 12: 13/15 already done, 2 left. Next bug: BUG-64 - `tools/secret_scanner.py` silently skips large text files
- Window 13: 7/9 already done, 2 left. Next bug: BUG-91 - Backend validation tools ignore stdout/stderr side effects and can leak secret-bearing output while reporting green or handled results
- Window 14: 4/10 already done, 6 left. Next bug: BUG-34 - `property_turn_fuzzer.py` writes non-canonical `run.json`
- Window 15: 3/5 already done, 2 left. Next bug: BUG-96 - `harness_lattice.py` is a false-green sensitivity sweep that never checks whether lattice dimensions change the reply meaningfully

## Compiler Topology

- Window 16: Runtime and Core Precompiler | round 1 | upstreams: 1, 2, 3, 4, 5, 6, 7
- Window 17: Tooling and Guardrail Precompiler | round 1 | upstreams: 8, 9, 10, 11, 12, 13, 14, 15
- Window 18: Final Compiler | round 1 | upstreams: 16, 17

## Canonical Files

- Live worker queues: `workflow/queues/`
- Workflow summary: `workflow/STATUS.md`
- Machine-readable status: `workflow/BACKLOG_STATUS.json`
- Window routing config: `workflow/config/windows.json`
- Cycle handoff state: `workflow/state/cycle-seed.json`
- Execution intelligence: `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`
- Fast path wrappers: `workflow/scripts/start_window_turn.ps1` and `workflow/scripts/complete_window_turn.ps1`
