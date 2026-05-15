# Seed Sweep

**Goal:** detect variance/nondeterminism by running the same input across many seeds.

## What it checks
- Counts **unique replies** across the seed range.
- Summarizes reply length distribution and **p95 latency**.
- Helps catch accidental sources of nondeterminism (hidden globals, prompt drift, seed not plumbed).

## Usage
```bash
python tools/seed_sweep.py --issue ISSUE-YYYYMMDD-NNN --text "Explain 2F vs 1F" --seed-start 1 --seed-end 50
```

## Outputs
- `runs/<run_id>/seed_sweep_report.json`
- `runs/<run_id>/seed_sweep_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS (unique replies within threshold)
- 1 FAIL (too many unique replies)

## Notes
This does not claim the model *should* be identical across seeds for real backends.
It is primarily for detecting **unexpected** variance in deterministic harness mode.
