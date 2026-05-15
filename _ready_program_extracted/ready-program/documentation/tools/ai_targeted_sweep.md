# targeted_sweep

Runs a small, deterministic **offline** sweep of high-signal tools and writes a standard run bundle.

## Usage

```bash
python tools/targeted_sweep.py --issue ISSUE-YYYYMMDD-NNN
```

> **Known issue note (ISSUE-20260201-701):** if you do **not** set `DAEDALUS_RUNS_DIR`, the sweep writes into `./runs/` inside the repo and then runs `tools/doctor.py`, which will flag the repo as **not distribution-clean** — causing the sweep to exit **INCOMPLETE**.
>
> **Workaround (recommended):**
> ```bash
> PYTHONDONTWRITEBYTECODE=1 DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/targeted_sweep.py --issue ISSUE-YYYYMMDD-NNN --seed 1337
> ```



Optional:
- `DAEDALUS_RUNS_DIR=/path/to/runs` to control the runs root.

## Outputs

Writes to `runs/<run_id>/` (or the configured runs root):

- `targeted_sweep_report.json`
- `targeted_sweep_summary.md`
- `run.json`
- plus any helper artifacts created during the sweep (e.g., `dummy_overlay.zip`)

## Exit codes

- `0` PASS
- `1` FAIL
- `2` INCOMPLETE

