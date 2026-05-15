# selfcheck

Fast, network-free sanity check for the canonical interaction surface (`xyzgl.router.route_turn`).

## What it asserts
- router returns a non-empty `reply` with the required safety prefix
- router round-trips and clamps `input` deterministically
- backend/tutor/prompt metadata keeps the expected core fields
- default selfcheck keeps grounding off and the bounded case enforces max chars in/out

## Usage
```bash
python tools/selfcheck.py
python tools/selfcheck.py --issue ISSUE-YYYYMMDD-NNN
python tools/selfcheck.py --issue ISSUE-YYYYMMDD-NNN --seed 123
```

## Outputs (issue mode)
- `runs/<run_id>/selfcheck_report.json`
- `runs/<run_id>/selfcheck_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL
- 2 INCOMPLETE
