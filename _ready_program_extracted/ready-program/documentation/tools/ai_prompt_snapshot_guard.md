# prompt_snapshot_guard

Detects **silent prompt drift** by hashing a small set of canonical Tutor prompts.

## Why this exists

Small changes to markers, ordering, or protocol/grounding boundaries can break the
whole tutoring loop without obvious test failures. This guard provides a cheap,
deterministic regression check.

## Usage

Compare against existing snapshots:

```bash
python tools/prompt_snapshot_guard.py --issue ISSUE-YYYYMMDD-NNN
```

Update the baseline intentionally:

```bash
python tools/prompt_snapshot_guard.py --issue ISSUE-YYYYMMDD-NNN --update
```

## Outputs

- Baseline: `snapshots/prompt_snapshots.json`
- Report: `runs/<new_run_id>/prompt_snapshot_report.json`

Exit codes:
- `0` PASS
- `1` FAIL