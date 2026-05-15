# Start Here

This folder is the canonical workflow brain for the `18`-window system.

Before assigning any window, open these files in order:

1. `workflow/STATUS.md`
2. `workflow/config/windows.json`
3. `workflow/shared/operating-rules.md`
4. `workflow/shared/cycle-reset.md`
5. `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`
6. `workflow/WINDOW_SYSTEM_PROMPTS.md`
7. `workflow/CYCLE_ORCHESTRA_PROMPTS.md`

## Core Laws

- `workflow/STATUS.md` is the canonical cold-stop map.
- `workflow/config/windows.json` plus the current getter output are the only legal task selectors.
- `workflow/queues/` is the only executable worker backlog.
- `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md` is the strategy layer for the remaining backlog.
- Removed queue items, old zip names, and earlier chat memory are never authoritative.
- Window `18` is the only cycle closer.
- A cycle is not closed until `workflow/scripts/publish_cycle_handoff.ps1` succeeds and the workflow grounding validates cleanly.

## Window Topology

- Worker windows: `01` through `15`
- Runtime precompiler: `16`, fed by windows `01` through `07`
- Tooling-and-guardrail precompiler: `17`, fed by windows `08` through `15`
- Final compiler: `18`, fed by windows `16` and `17`

## Minimal Window Loop

1. Assign one window.
2. That window opens its role file, state file, and required shared files.
3. It runs `workflow/scripts/start_window_turn.ps1`.
4. If the wrapper reports `ready`, it performs exactly one legal unit of work.
5. It finishes with `workflow/scripts/complete_window_turn.ps1`, which packages the result, runs `workflow/scripts/verify_package_manifest.ps1`, updates state, and optionally publishes the cycle handoff.
6. It replies in the required one-line or three-line format and stops.

Fast path:

- workers: `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed`
- compilers: `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed -CreateNoOps`
- sync-only: `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed -SyncOnly`
- finish: `workflow/scripts/complete_window_turn.ps1 ...`

## Output Contract

- Worker windows `01` through `15`: one explicit absolute filesystem link to the package directory only.
- Precompiler windows `16` and `17`: one explicit absolute filesystem link to the package directory only.
- Window `18`: exactly three lines only:
  - final package directory path
  - ready-program artifact path
  - backward-sync patch path
- Wait or blocker replies: one short line naming the missing upstream item and including the most relevant explicit absolute filesystem link.

## Cycle Restart Rule

After a successful window `18` merge:

1. window `18` runs `workflow/scripts/publish_cycle_handoff.ps1`
2. that script publishes the ready-program artifact and backward-sync patch
3. it promotes the cycle seed
4. it trims completed queue items
5. it resets compiler rounds and refreshes the cold-stop files
6. it validates the workflow grounding
7. lagging windows `01` through `17` apply the cycle seed on their next sync-only or normal getter pass

Do not manually repost the whole repo into lagging windows once this workflow is in use.
Use the handoff artifacts instead.
