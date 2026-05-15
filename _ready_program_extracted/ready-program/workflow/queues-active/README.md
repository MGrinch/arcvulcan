# Active Queues

This folder contains the live unresolved worker queues for the current integrated snapshot.

- Source queues remain archived under `workflow/queues/`.
- Each active item keeps `original_queue_index` so you can trace it back to the archived full backlog.
- `workflow/config/windows.json` now points worker windows at these active queue JSON files.
- See `workflow/STATUS.md` and `workflow/BACKLOG_STATUS.json` for the audit summary.
