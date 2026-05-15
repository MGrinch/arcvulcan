# graph_invariant_checker

Validates **knowledge graph invariants** in `knowledge_graph.json` and (when
present) cross-checks against `session_report.json`.

## What it checks

- Unique `node_id`
- `confidence` in `[0..1]`
- `last_verified_turn >= -1`
- Optional: `last_verified_turn` does not exceed the session's max turn index

## Usage

```bash
python tools/graph_invariant_checker.py --issue ISSUE-YYYYMMDD-NNN runs/<run_id>/
```

## Outputs

- `runs/<new_run_id>/graph_invariant_report.json`

Exit codes:
- `0` PASS
- `1` FAIL
- `2` INCOMPLETE