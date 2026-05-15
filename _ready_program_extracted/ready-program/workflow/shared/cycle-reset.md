# Cycle Reset

Use this file when a cycle ends and a new cycle begins from the latest integrated build.

Rules:

- Reground at the start of every session, then again only when the cycle seed changes or the user reassigns your window.
- Do not reground after every `next`. That adds drift without improving determinism.
- The cycle seed is the backward-sync patch emitted from the latest post-compiler handoff. Every window from `01` through `17` may need it at the start of a new cycle.

Cycle handoff:

1. Complete the normal window `18` final compile and package the final merge result.
2. Run `workflow/scripts/publish_cycle_handoff.ps1 -PackagePath <window-18-final-package-dir>`.
3. That handoff must produce:
   - a ready-program artifact under `workflow/handoffs/cycle-XX/ready-program/`
   - a backward-sync patch under `workflow/handoffs/cycle-XX/backward-sync-patch/`
   - a workflow grounding validation report at `workflow/handoffs/cycle-XX/workflow-validation.json`
   - a refreshed cycle seed in `workflow/state/cycle-seed.json`
   - rewritten unresolved queues and cold-stop status files
4. Assign the next window as usual.
5. Run the normal getter:
   - preferred fast path: `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed`
   - low-level path: `workflow/scripts/get_next_worker_item.ps1 -Window <N>` for workers or `workflow/scripts/get_next_merge_batch.ps1 -Window <N> -CreateNoOps` for compiler windows
6. If the getter returns `seed-required`, run `workflow/scripts/apply_cycle_seed.ps1 -Window <N>`, or let `start_window_turn.ps1 -AutoApplySeed` do it for you.
7. Continue normal work and finish with `workflow/scripts/complete_window_turn.ps1`.

Notes:

- `workflow/scripts/publish_cycle_handoff.ps1` is the canonical post-cycle script. It emits the shareable ready-program artifact and the backward-sync patch, validates the workflow grounding, then updates the cycle seed and cold-stop files together.
- `set_cycle_seed.ps1` still exists as the low-level seed writer, but normal cycle closes should go through `publish_cycle_handoff.ps1`.
- Window `18` is the post-compiler. Windows `16` and `17` are the two precompilers.
- Window `16` owns the seven-window runtime side (`1` through `7`).
- Window `17` owns the eight-window tooling and guardrail side (`8` through `15`).
