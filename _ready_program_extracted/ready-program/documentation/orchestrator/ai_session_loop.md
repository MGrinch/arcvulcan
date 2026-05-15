# ai_session_loop

Session orchestration is a **thin state machine** that composes:

- Tutor backend calls (TEACH + EVAL)
- Optional Mirror prediction
- Deterministic node selection + closure heuristics

Code surfaces:
- `xyzgl/orchestrator/session_loop.py` — `run_session(...)`
- `xyzgl/orchestrator/turn.py` — TEACH/EVAL phase calls
- `xyzgl/orchestrator/policies.py` — state + budget + closure heuristic

## Turn structure

Each orchestrated turn captures:

- **TEACH**: Tutor produces a teaching block and a single question.
- **MIRROR** (optional): Mirror predicts a plausible learner answer.
- **USER**: Input provider returns the real learner answer + optional telemetry.
- **EVAL**: Tutor compares mirror vs real; emits evaluation and either:
  - `NEXT_ACTION: CLOSE_NODE` or
  - `NEXT_ACTION: PROBE` + a `Q2` pointed question.

The v0 session loop reuses the same teaching block and keeps probing the same node until it closes.

## Protocol re-grounding

Tutor prompts are built via `xyzgl.prompting.build_tutor_prompt(...)`, so `protocol_reground_every` is enforced across session turns.

## Harness

Use `python tools/harness_session.py --issue ISSUE-...` to generate a deterministic run bundle.
