# ArcVulcan (XYZGL Engine) - Recovery Pack

**ArcVulcan** is the current project name for the deterministic welding-tutor system formerly referred to as **Project Daedalus / XYZGL**.

This pack emphasizes the current state of the codebase: **run-bundle sealed**, **schema-validated**, **audit-first**, and now grounded for the `18`-window development workflow.

## Goals

- keep the project runnable
- preserve deterministic, replayable tutoring behavior
- keep workflow state and queue state aligned with the real integrated program
- let a multi-window patch farm continue from the live code without reposting stale repo copies

## Quick Start

```bash
python tools/doctor.py
python tools/harness_turn.py --issue ISSUE-20260129-001
python tools/validate_schemas.py runs/<run_id>/
```

## Chat Window Mode

For the multi-window autonomous patch workflow, upload the whole repo zip and start with [00_WINDOW_FARM_START_HERE.md](./00_WINDOW_FARM_START_HERE.md).

After assigning `window N`, each `next` advances that same window by exactly one queued bug or merge round. The current topology is:

- worker windows `01` through `15`
- precompiler windows `16` and `17`
- final compiler window `18`

Cycle closes are authoritative only through `workflow/scripts/publish_cycle_handoff.ps1`, which must publish:

- the final package
- a ready-program artifact for fresh windows
- a backward-sync patch for lagging windows
- refreshed cold-stop files for the next cycle

This snapshot already has a trimmed live backlog plus strategy guidance for the remaining work. See `workflow/STATUS.md` for the exact restart point, `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md` for the backlog strategy layer, `workflow/WINDOW_SYSTEM_PROMPTS.md` for per-window prompts, and `workflow/CYCLE_ORCHESTRA_PROMPTS.md` for the cycle run order.

Fast path wrappers for the workflow:

- `workflow/scripts/start_window_turn.ps1`
- `workflow/scripts/complete_window_turn.ps1`

## Structure

- `xyzgl/` core tutoring plus routing layer
- `witness/` crash-to-report envelope plus PII scrubbing
- `tools/` runnable debug harnesses plus schema validation
- `schemas/` JSON Schemas for harness outputs
- `tests/` regression and contract coverage for the tutoring engine and tooling
- `curriculum/` local grounding corpus plus retrieval benchmark inputs
- `documentation/` design plus usage docs
- `workflow/` active multi-window development workflow, queues, packaging scripts, and operator grounding
