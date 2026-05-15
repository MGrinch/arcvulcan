# Atheris Fuzz Router

**Goal:** fuzz `xyzgl.router.route_turn()` to catch crashes and sharp edges.

## What it does
- If `atheris` is installed, runs a bounded libFuzzer session against `route_turn()`.
- If `atheris` is missing, runs a deterministic **fallback fuzzer** (fixed case count derived from `--seconds`).

## Usage
```bash
python tools/atheris_fuzz_router.py --issue ISSUE-YYYYMMDD-NNN --seconds 10
```

## Outputs
- `runs/<run_id>/atheris_fuzz_report.json`
- `runs/<run_id>/atheris_fuzz_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL
