# Protocol Drift Radar

**Goal:** detect role-boundary drift across multi-turn runs.

This tool scans `turn_report.json` and/or `session_report.json` and emits a
heuristic list of findings (WARN / HIGH).

## Usage
```bash
python tools/protocol_drift_radar.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN
```

## Outputs

> **Audit bundle note (ISSUE-20260201-702):** on missing/invalid input paths, this tool exits non-zero **without writing a run bundle** unless `DAEDALUS_RUNS_DIR` is set (so it can write outside the repo).  
> If you need an audit trail for failures, run with:
> ```bash
> PYTHONDONTWRITEBYTECODE=1 DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/protocol_drift_radar.py --issue ISSUE-YYYYMMDD-NNN <args>
> ```

- `runs/<run_id>/protocol_drift_report.json`
- `runs/<run_id>/protocol_drift_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS (no HIGH findings)
- 1 FAIL (HIGH findings)
- 2 INCOMPLETE (no recognizable artifacts)