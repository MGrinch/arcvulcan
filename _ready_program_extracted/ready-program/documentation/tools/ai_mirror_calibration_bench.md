# Mirror Calibration Bench

**Goal:** measure how closely the Mirror prediction matches the learner answer.

## What it checks
- Computes similarity metrics (token Jaccard, SequenceMatcher ratio) between:
  - `turns[*].mirror.answer`
  - `turns[*].eval.user_answer`

## Usage
```bash
python tools/mirror_calibration_bench.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN
```

Fail below a threshold:
```bash
python tools/mirror_calibration_bench.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN --min-avg 0.35
```

## Outputs
- `runs/<run_id>/mirror_calibration_report.json`
- `runs/<run_id>/mirror_calibration_summary.md`
- `runs/<run_id>/run.json`

Known issue: `run.json.outputs` may omit `mirror_calibration_summary.md`; see `ISSUE-20260202-704`.

## Exit codes
- 0 PASS
- 1 FAIL (avg below threshold)
- 2 INCOMPLETE (no mirror answers)
