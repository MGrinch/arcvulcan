# Mirror Leakage Detector

**Goal:** ensure the Mirror stays in the learner-simulator role (does not teach).

## What it checks
- Scans `turns[*].mirror.answer` for common imperative/teaching patterns.
- Flags turns where the Mirror sounds like a tutor.

## Usage
```bash
python tools/mirror_leakage_detector.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN
```

## Outputs
- `runs/<run_id>/mirror_leakage_report.json`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL (role leakage)
- 2 INCOMPLETE (no mirror answers)