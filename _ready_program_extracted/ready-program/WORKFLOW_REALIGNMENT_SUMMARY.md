# Workflow Realignment Summary

This snapshot contains the realigned DAEDALUS program and workflow grounding as of `2026-03-20`.

## What Was Updated

- The window farm is normalized to `18` windows:
  - workers `01` through `15`
  - precompilers `16` and `17`
  - final compiler `18`
- The temporary worker-16 certification lane was collapsed back into the main worker topology, and its backlog was redistributed into the original owning windows.
- Worker queues now contain only unresolved items and carry stronger window-level doctrine plus richer bug-level missions.
- `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md` explains the strategic intent and robust acceptance bar for every still-open bug.
- `workflow/STATUS.md` and `workflow/BACKLOG_STATUS.json` reflect the real cold-stop position for the 18-window topology.
- Cycle handoff rules require window `18` to publish:
  - the final package
  - a ready-program artifact for grounding fresh windows
  - a backward-sync patch for lagging windows
- The standard fast path remains:
  - `workflow/scripts/start_window_turn.ps1`
  - `workflow/scripts/complete_window_turn.ps1`
- The cycle handoff ordering still ensures the ready-program snapshot is copied after the queue/state reset and seed rewrite, not before.
- `workflow/scripts/repartition_workflow_topology.ps1` remains the operator alias for rebasing the live workflow topology.

## Current Restart Point

See `workflow/STATUS.md`.

At this snapshot:

- active cycle is still whatever `workflow/state/cycle-seed.json` records
- workers restart from unresolved round `1`
- compiler windows `16`, `17`, and `18` are reset to round `1`

## Canonical Workflow Files

- `workflow/STATUS.md`
- `workflow/BACKLOG_STATUS.json`
- `workflow/config/windows.json`
- `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`
- `workflow/WINDOW_SYSTEM_PROMPTS.md`
- `workflow/CYCLE_ORCHESTRA_PROMPTS.md`
- `workflow/shared/operating-rules.md`
- `workflow/shared/cycle-reset.md`

## Cycle Close Rule

After every successful window `18` final compile:

1. package the final merge result
2. run `workflow/scripts/publish_cycle_handoff.ps1 -PackagePath <final package dir>`
3. validate the workflow grounding
4. use the ready-program artifact to ground fresh windows
5. use the backward-sync patch as the cycle seed for lagging windows `01` through `17`

## Intended Use

Use this folder as the canonical grounding folder for the `18`-window workflow.
