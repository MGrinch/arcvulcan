# CI Gate

**Goal:** run a small deterministic battery of checks that exercises the full session loop.

## What it runs
1. `tools/doctor.py`
2. `tools/selfcheck.py`
3. `tools/backend_contract_probe.py`
4. `tools/harness_session.py` (stub tutor + stub mirror + local grounding)
5. `tools/validate_schemas.py` (on the session run)
6. `tools/protocol_drift_radar.py`
7. `tools/mirror_leakage_detector.py`
8. `tools/mirror_calibration_bench.py`
9. `tools/ontario_claims_citation_guard.py --enforce`

## Usage
```bash
python tools/ci_gate.py --issue ISSUE-YYYYMMDD-NNN
```

> **Known issue note (ISSUE-20260201-703):** `ci_gate` currently extracts the session run directory from `harness_session` output using a regex that expects the path to include a directory named `runs` or `daedalus_runs`.  
> If you set `DAEDALUS_RUNS_DIR` to something like `/tmp/runs_out`, `ci_gate` may report **INCOMPLETE** (`could not locate session run dir`).  
> **Workaround:** use a runs root whose directory name includes `runs` or `daedalus_runs` (e.g. `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs`).



## Outputs
- `runs/<run_id>/ci_gate_report.json`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL
- 2 INCOMPLETE