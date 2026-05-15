# ai_debug_harness_session

**IMPLEMENTATION (2026-01-30): tool is runnable**

Runs a deterministic **multi-turn session** through the orchestrator (`xyzgl.orchestrator.session_loop.run_session`) and writes a run bundle.

This harness exists to prove the session loop wiring works *without network credentials*.

## Usage

```bash
python tools/harness_session.py --issue ISSUE-YYYYMMDD-NNN
```

Optional:
```bash
python tools/harness_session.py --issue ISSUE-YYYYMMDD-NNN --seed 1337 --max-turns 6 --protocol-reground-every 5 --enable-mirror
```

Enable local grounding (reads `curriculum/manifest.json` + local text passages):
```bash
python tools/harness_session.py --issue ISSUE-YYYYMMDD-NNN --grounding
```

Outputs:

> **Scaling note (ISSUE-20260202-705):** `session_report.json` grows linearly with `--max-turns` and can become large for long runs (e.g., ~15.7 MB at 10,000 turns in stub mode). Keep `--max-turns` modest in CI; for very long simulations prefer streamed/rotating logs (not yet implemented).


- `runs/<run_id>/session_report.json` (WitnessEvent containing payload.session_report)
- `runs/<run_id>/knowledge_graph.json`
- `runs/<run_id>/session_summary.md`
- `runs/<run_id>/run.json`

Exit codes:
- `0` PASS, `1` FAIL, `2` INCOMPLETE

Deterministic:
- uses `--seed`
- protocol reground cadence defaults to config (5) unless `--protocol-reground-every` is set
- forces `GWEN_DISABLED=1`

## Recommended follow-ups

Validate outputs:
```bash
python tools/validate_schemas.py runs/<run_id>/
```
