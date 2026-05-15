# Cycle Orchestra Prompts

Use `workflow/WINDOW_SYSTEM_PROMPTS.md` for the full per-window prompts.
This file is the short operator sheet for running all `18` windows as one cycle.

## Canonical Cycle Order

1. Ground each chat window with its matching prompt from `workflow/WINDOW_SYSTEM_PROMPTS.md`.
2. Run worker windows `01` through `15` until each one produces exactly one package or replies `WINDOW NN COMPLETE`.
3. Paste outputs from windows `01` through `07` into window `16`.
4. Paste outputs from windows `08` through `15` into window `17`.
5. Run window `16` once the runtime-side worker round is ready.
6. Run window `17` once the tooling-side worker round is ready.
7. Paste the outputs from windows `16` and `17` into window `18`.
8. Run window `18` once both precompiler outputs are ready.
9. Window `18` must immediately run the cycle handoff and emit three lines:
   - final package path
   - ready-program artifact path
   - backward-sync patch path
10. Use the ready-program artifact for any fresh window.
11. Paste the backward-sync patch into lagging windows `01` through `17`, then run a sync-only pass before their next compute step.

## Minimal Operator Loop

- Workers `01` through `15`: paste `next`
- Precompilers `16` and `17`: paste `next` only after their upstream package set is present
- Final compiler `18`: paste `next` only after both precompiler package sets are present
- After cycle close: paste the backward-sync patch into windows `01` through `17`, then use the sync-only prompt once

## Sync-Only Use

Use the sync-only prompts:

- after a new window `18` handoff
- when a window has been idle across a cycle boundary
- when a window was grounded against an older repo state

## Worker Sync-Only Prompt

```text
You are Window NN.
Persist identity as window NN for the full thread.
This is a sync-only pass. Do not complete a new bug in this turn.

1. Open workflow/STATUS.md, workflow/config/windows.json, your role file, workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md, your queue file, your state file, workflow/shared/operating-rules.md, and workflow/shared/cycle-reset.md.
2. Run workflow/scripts/start_window_turn.ps1 -Window NN -AutoApplySeed -SyncOnly.
3. Stop after the seed check or seed apply. Do not edit code or package anything in this turn.
4. Reply with one short line only:
WINDOW NN SYNCED <status> <round-or-cycle> <absolute filesystem path to the applied seed package, or to your state file if no seed was needed>
```

## Compiler Sync-Only Prompt

```text
You are Window NN.
Persist identity as window NN for the full thread.
This is a sync-only pass. Do not complete a new merge batch in this turn.

1. Open workflow/STATUS.md, workflow/config/windows.json, your role file, your state file, workflow/shared/operating-rules.md, and workflow/shared/cycle-reset.md.
2. Run workflow/scripts/start_window_turn.ps1 -Window NN -AutoApplySeed -SyncOnly.
3. Stop after the seed check or seed apply. Do not package anything in this turn.
4. Reply with one short line only:
WINDOW NN SYNCED <status> <round-or-cycle> <absolute filesystem path to the applied seed package, or to your state file if no seed was needed>
```

## Final Cycle-Close Rule

```text
After every successful window 18 final compile:
1. Finish with workflow/scripts/complete_window_turn.ps1 -PublishCycleHandoff.
2. Ensure the handoff emits the ready-program artifact, backward-sync patch, and workflow-validation report.
3. Reply with exactly three lines only:
   - final package directory path
   - ready-program artifact path
   - backward-sync patch path
```
