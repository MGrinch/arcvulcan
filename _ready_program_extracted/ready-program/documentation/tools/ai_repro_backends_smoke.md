# repro_backends_smoke

Fast smoke test for tutor/mirror backend wiring (network-free by default).

## Usage
- From repo root:
  - `python tools/repro_backends_smoke.py --issue ISSUE-YYYYMMDD-NNN`

## Outputs
- Prints PASS/FAIL/INCOMPLETE to stdout.

## Exit codes
- 0: PASS
- 1: FAIL
- 2: INCOMPLETE (e.g., backend not available in current environment)

## Notes
- Designed to run in CI and in zipped distributions.
