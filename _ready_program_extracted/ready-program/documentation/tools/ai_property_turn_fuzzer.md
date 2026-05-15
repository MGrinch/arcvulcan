# property_turn_fuzzer

Runs a deterministic fuzz battery against `xyzgl.router.route_turn()`.

## What it catches

- crashes on weird unicode / marker-like strings
- missing keys in the `route_turn()` contract
- prompt marker regressions that bubble into the reply

## Usage

Builtin deterministic fuzzing:

```bash
python tools/property_turn_fuzzer.py --issue ISSUE-YYYYMMDD-NNN --cases 200
```

Hypothesis mode (if installed):

```bash
python tools/property_turn_fuzzer.py --issue ISSUE-YYYYMMDD-NNN --hypothesis
```

## Outputs

- `runs/<new_run_id>/property_fuzz_report.json`

Exit codes:
- `0` PASS
- `1` FAIL
- `2` INCOMPLETE