# Artifact Round-Trip

**Goal:** sanity-check JSON artifacts for parseability and stable serialization.

## What it checks
- JSON parses cleanly (no partial writes / corruption).
- Re-serialization produces valid JSON.
- Optional strict mode can fail when the canonical serialization differs.

## Usage
Check a run directory:
```bash
python tools/artifact_roundtrip.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN
```

Check a single file:
```bash
python tools/artifact_roundtrip.py runs/<run_id>/turn_report.json --issue ISSUE-YYYYMMDD-NNN
```

Fix (rewrite canonical JSON):
```bash
python tools/artifact_roundtrip.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN --fix
```

## Outputs

> **Audit bundle note (ISSUE-20260201-702):** on missing/invalid input paths, this tool exits non-zero **without writing a run bundle** unless `DAEDALUS_RUNS_DIR` is set (so it can write outside the repo).  
> If you need an audit trail for failures, run with:
> ```bash
> PYTHONDONTWRITEBYTECODE=1 DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/artifact_roundtrip.py --issue ISSUE-YYYYMMDD-NNN <args>
> ```

- `runs/<run_id>/artifact_roundtrip_report.json`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL
