# redteam_injection_suite

Runs a curated set of **prompt-injection attacks** against the Tutor path and
checks for obvious boundary regressions.

## Notes

- This is a regression detector, not a security audit.
- With the stub tutor backend, the main value is catching marker or prompt
  assembly mistakes.

## Usage

```bash
python tools/redteam_injection_suite.py --issue ISSUE-YYYYMMDD-NNN
```

## Outputs

- `runs/<new_run_id>/redteam_injection_report.json`

Exit codes:
- `0` PASS
- `1` FAIL