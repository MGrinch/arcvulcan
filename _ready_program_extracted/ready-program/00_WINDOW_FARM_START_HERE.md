# Window Farm Start Here

Use this file as the root operator entrypoint for the `18`-window workflow.

## Authoritative Files

Read these in order before starting or restarting any window:

1. `workflow/STATUS.md`
2. `workflow/config/windows.json`
3. `workflow/START_HERE.md`
4. `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`
5. `workflow/WINDOW_SYSTEM_PROMPTS.md`
6. `workflow/CYCLE_ORCHESTRA_PROMPTS.md`

Trust the current local repo state and the current getter output only.
Do not trust old zip names, earlier chat memory, removed queue items, or stale notes.

## Minimal Operator Loop

1. Upload this whole repo zip or open this whole repo folder in one chat window per worker/compiler.
2. Ground each chat with the matching prompt from `workflow/WINDOW_SYSTEM_PROMPTS.md`.
3. Use `next` to advance exactly one legal unit of work in that window.
4. Prefer the standard wrappers inside each window:
   - `workflow/scripts/start_window_turn.ps1`
   - `workflow/scripts/complete_window_turn.ps1`
5. Let worker windows `01` through `15` each produce one package or reply `WINDOW NN COMPLETE`.
6. Let window `16` merge the runtime-side packages from windows `01` through `07`.
7. Let window `17` merge the tooling-side packages from windows `08` through `15`.
8. Let window `18` merge the outputs from `16` and `17`.
9. After every successful window `18` merge, use the emitted handoff artifacts:
   - the ready-program artifact for fresh windows
   - the backward-sync patch for lagging windows `01` through `17`
10. At the start of the next cycle, run a sync-only pass so each lagging window can apply the new cycle seed before doing more work.

## Expected Replies

- Worker windows `01` through `15`: one explicit absolute filesystem link to the produced package directory only.
- Precompiler windows `16` and `17`: one explicit absolute filesystem link to the produced package directory only.
- Window `18`: exactly three lines only:
  - final package directory path
  - ready-program artifact path
  - backward-sync patch path
- Blocked or waiting windows: one short line naming the missing upstream file/window and including the most relevant explicit absolute filesystem link.
- Exhausted queues: `WINDOW NN COMPLETE`

## Cycle Close Rule

Window `18` is responsible for closing the cycle. After every successful final merge it must:

1. package the final merge result
2. verify the final package manifest
3. run `workflow/scripts/publish_cycle_handoff.ps1 -PackagePath <final package dir>`
4. produce the three output paths
5. leave the repo in a rewritten cold-stop state for the next cycle

That handoff is the only legal way to:

- publish the next ready-program snapshot
- publish the backward-sync patch
- promote the cycle seed
- trim completed queue items
- reset compiler rounds
- refresh `workflow/STATUS.md` and `workflow/BACKLOG_STATUS.json`
- validate the workflow grounding after cycle close

Do not manually repost the whole live repo into lagging windows after cycle close.
Use the backward-sync patch through the normal cycle-seed flow instead.
