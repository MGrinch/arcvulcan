# repro_replay_diff

Replays a prior run and compares key artifacts to detect **non-determinism** or
unexpected behavior changes.

## Supported inputs

- `runs/<run_id>/turn_report.json`
- `runs/<run_id>/session_report.json` (best-effort deterministic replay on stub)

## Usage

```bash
python tools/repro_replay_diff.py --issue ISSUE-YYYYMMDD-NNN runs/<run_id>/
```

## Outputs

> **Audit bundle note (ISSUE-20260201-702):** on missing/invalid input paths, this tool exits non-zero **without writing a run bundle** unless `DAEDALUS_RUNS_DIR` is set (so it can write outside the repo).  
> If you need an audit trail for failures, run with:
> ```bash
> PYTHONDONTWRITEBYTECODE=1 DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/repro_replay_diff.py --issue ISSUE-YYYYMMDD-NNN <args>
> ```


- `runs/<new_run_id>/replay_diff_report.json`

Exit codes:

- `0` PASS
- `1` FAIL
- `2` INCOMPLETE