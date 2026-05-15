# Node Evolution Diff

**Goal:** compare two `knowledge_graph.json` snapshots and summarize node changes.

## What it checks
- Added/removed node ids
- Field diffs on shared nodes (confidence, last_verified_turn, fragility_flags, etc.)
- Optional linking of `CLOSE_NODE` actions if you pass a `session_report.json`

## Usage
```bash
python tools/node_evolution_diff.py before.json after.json --issue ISSUE-YYYYMMDD-NNN
```

With session linking:
```bash
python tools/node_evolution_diff.py before.json after.json --issue ISSUE-YYYYMMDD-NNN --session-report runs/<run_id>/session_report.json
```

## Outputs

> **Audit bundle note (ISSUE-20260201-702):** on missing/invalid input paths, this tool exits non-zero **without writing a run bundle** unless `DAEDALUS_RUNS_DIR` is set (so it can write outside the repo).  
> If you need an audit trail for failures, run with:
> ```bash
> PYTHONDONTWRITEBYTECODE=1 DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/node_evolution_diff.py --issue ISSUE-YYYYMMDD-NNN <args>
> ```

- `runs/<run_id>/node_evolution_report.json`
- `runs/<run_id>/node_evolution_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL (missing inputs)