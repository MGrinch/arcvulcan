# Worker Queues

This is the canonical live worker backlog for this repo snapshot.

- Every JSON file here contains only unresolved items.
- `completed_items_removed` tells you how many queued items were already accomplished before execution was interrupted.
- The old duplicate full backlog files were removed; `original_queue_index` preserves where each unfinished bug sat when execution stopped.
- After every successful window `14` cycle close, `workflow/scripts/rebase_unresolved_backlog.ps1` removes the just-finished worker items from these queues and resets the next cycle to round `1`.
- See `workflow/STATUS.md` for the exact restart point for each window.
