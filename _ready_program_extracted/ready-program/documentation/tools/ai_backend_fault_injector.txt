# Backend Fault Injector

**Goal:** deterministically exercise backend failure modes so the router and
session loop remain stable.

## What it checks
- Misconfigured **Gemini** tutor backend falls back to stub and reports
  `backend_error`.
- With `DAEDALUS_REQUIRE_REAL_BACKENDS=1`, misconfig raises (strict mode).
- Runtime failures from the Tutor are tolerated (fallback) unless strict mode.
- Mirror failures are tolerated and reported.

## Usage
```bash
python tools/backend_fault_injector.py --issue ISSUE-YYYYMMDD-NNN
```

## Outputs
- `runs/<run_id>/backend_fault_report.json`
- `runs/<run_id>/backend_fault_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS (all scenarios matched expectations)
- 1 FAIL (a scenario diverged)
- 2 INCOMPLETE (reserved for missing imports)

## Notes
The tool uses the special `fault` backend for deterministic injected errors:
`DAEDALUS_TUTOR_BACKEND=fault` and `DAEDALUS_FAULT_MODE=exception|timeout|empty|slow`.