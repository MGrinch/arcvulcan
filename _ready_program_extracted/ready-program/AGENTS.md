# Window Workflow

If the user assigns a window number from `1` to `18`, switch into the local workflow stored under `workflow/`.

This snapshot already matches the unresolved backlog that remains after earlier merged work.
The canonical restart map lives in `workflow/STATUS.md`, and the canonical routing map lives in `workflow/config/windows.json`.
Do not revive previously completed queue items from memory, old zip names, or historical notes.

## Grounding Order

1. Open `workflow/STATUS.md`.
2. Open `workflow/config/windows.json`.
3. Find the matching window entry.
4. Open that entry's `role_file` and `state_file`.
5. Open `workflow/shared/operating-rules.md`, `workflow/shared/package-format.md`, and `workflow/shared/cycle-reset.md`.
6. If the window is a compiler, also open `workflow/shared/merge-rules.md`.
7. If the window is a worker, also open `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md` and the window's `queue_file`.
8. Persist that window number for the rest of the thread. If the user later says `next`, keep using that same window unless they explicitly change it.

## Execution Rules

- Worker windows `1` to `15`:
  - Prefer `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed`.
  - Run `workflow/scripts/get_bug_section.ps1 -BugId <BUG-ID>` for only the current bug.
  - Read the matching queue item metadata and the matching section in `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`.
  - Fix exactly one queued bug.
  - Finish with `workflow/scripts/complete_window_turn.ps1`.
  - Reply with the explicit absolute filesystem link to the package directory only.

- Precompiler windows `16` and `17`:
  - Prefer `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed -CreateNoOps`.
  - If a batch is ready, apply the returned packages with `workflow/scripts/apply_patch_package.ps1`, resolve deliberate overlaps, create a merged package, verify it with `workflow/scripts/verify_package_manifest.ps1`, update state, and reply with the explicit absolute filesystem link to the package directory only.
  - If upstream work is missing, reply with one short wait line naming the missing window and round, and include the explicit absolute filesystem link to the most relevant existing package or input file used in that compute step.

- Final compiler window `18`:
  - Prefer `workflow/scripts/start_window_turn.ps1 -Window 18 -AutoApplySeed -CreateNoOps`.
  - If a batch is ready, merge windows `16` and `17`, then finish with `workflow/scripts/complete_window_turn.ps1 -PublishCycleHandoff`.
  - Successful replies from window `18` must use exactly three lines only:
    - final package path
    - ready-program artifact path
    - backward-sync patch path
  - If upstream work is missing, reply with one short wait line naming the missing window and round, and include the explicit absolute filesystem link to the most relevant existing package or input file used in that compute step.

- If a worker queue is exhausted, reply `WINDOW NN COMPLETE`.
- Do not switch queues unless the user explicitly changes the window number.
- Do not add summaries after package-path replies.

For requests unrelated to the window workflow, behave normally.
