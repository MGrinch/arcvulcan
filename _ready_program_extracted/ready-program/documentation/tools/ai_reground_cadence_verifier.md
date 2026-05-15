# reground_cadence_verifier

Verifies that the **ROLE_PROTOCOL re-grounding cadence** matches expectations.

## What it checks

- Turn 0 should be regrounded.
- Then every **N turns** (default `--every 5`).
- For session runs, it checks **both** TEACH and EVAL phase prompt metas.

## Usage

```bash
python tools/reground_cadence_verifier.py --issue ISSUE-YYYYMMDD-NNN --every 5 runs/<run_id>/
```

You can also point it at a single report JSON:

```bash
python tools/reground_cadence_verifier.py --issue ISSUE-YYYYMMDD-NNN --every 5 runs/<run_id>/session_report.json
```

## Outputs

Writes:
- `runs/<new_run_id>/reground_cadence_report.json`

Exit codes:
- `0` PASS
- `1` FAIL
- `2` INCOMPLETE
