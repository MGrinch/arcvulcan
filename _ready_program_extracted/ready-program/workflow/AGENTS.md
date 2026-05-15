# Chat Window Workflow Folder

This folder is the single grounding folder for chat windows `1` through `18`.

This workflow has already been rebaselined onto the unresolved backlog that matches the integrated code snapshot. See `STATUS.md` for the exact cold-stop position before starting a window.

Assume:

- this folder is `workflow/`
- the program root is the parent folder `..`
- all bug work, merges, packaging, and cycle-close state changes are driven from files in this folder

When the user assigns window `N` in any direct form such as `window 7`, `you are chat window 7`, or just `7`, do this immediately:

1. Open `STATUS.md`.
2. Open `config/windows.json`.
3. Find window `N`.
4. Open the window's `role_file` and `state_file`.
5. Open `shared/operating-rules.md`, `shared/package-format.md`, and `shared/cycle-reset.md`.
6. If `N` is a compiler window, also open `shared/merge-rules.md`.
7. If `N` is a worker window, also open `UNRESOLVED_EXECUTION_INTELLIGENCE.md` and the window's `queue_file`.
8. Persist that window number for the rest of the thread. If the user later says `next`, keep using the same window unless they explicitly change it.

Execution rules:

- Windows `1` to `15`:
  - Prefer `scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed`.
  - If you need the low-level path, run `scripts/get_next_worker_item.ps1 -Window <N>` and apply the cycle seed manually if required.
  - Run `scripts/get_bug_section.ps1 -BugId <BUG-ID>`.
  - Fix exactly one bug in the parent program root.
  - Finish with `scripts/complete_window_turn.ps1`.
  - Reply with the explicit absolute filesystem link to the package directory only.

- Windows `16` and `17`:
  - Prefer `scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed -CreateNoOps`.
  - If ready, apply upstream packages with `scripts/apply_patch_package.ps1`, then finish with `scripts/complete_window_turn.ps1`.
  - If not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem link to the most relevant existing package or input file used in that compute step.

- Window `18`:
  - Prefer `scripts/start_window_turn.ps1 -Window 18 -AutoApplySeed -CreateNoOps`.
  - If ready, merge windows `16` and `17`, then finish with `scripts/complete_window_turn.ps1 -PublishCycleHandoff`.
  - Successful replies from window `18` must use three lines only: final package path, ready-program artifact path, backward-sync patch path.
  - If not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem link to the most relevant existing package or input file used in that compute step.

- If a worker queue is exhausted, reply `WINDOW NN COMPLETE`.
- Do not switch queues unless the user explicitly changes the window number.
