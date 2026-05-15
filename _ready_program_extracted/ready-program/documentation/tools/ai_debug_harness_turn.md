# ai_debug_harness_turn

**IMPLEMENTATION (2026-01-07): tool is runnable**

Runs a deterministic single turn through `xyzgl.router.route_turn()` and writes a run bundle.

## Usage

```bash
python tools/harness_turn.py --issue ISSUE-20260129-002
```

Optional:
```bash
python tools/harness_turn.py --issue ISSUE-20260129-002 --seed 1337 --text "fit-up is uneven, should I keep tacking?"
```

Outputs:
- `runs/<run_id>/turn_report.json` (WitnessEvent containing payload.turn_result)
- `runs/<run_id>/turn_summary.md`
- `runs/<run_id>/run.json`

Exit codes:
- `0` PASS, `1` FAIL, `2` INCOMPLETE

Deterministic:
- uses `--seed`
- forces `GWEN_DISABLED=1`
- deletes temp storage unless `--keep-storage` (if added later)

## Recommended follow-ups

Validate outputs:
```bash
python tools/validate_schemas.py runs/<run_id>/
```
