# Active Queue: Window 07

- Name: Replay Diff and Bundle Integrity
- Area: Owns replay-diff behavior, strict replay semantics, and replay-facing bundle integrity bugs.
- Archived source queue: `queues/window-07.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 4

1. BUG-111 | original #3 | phase 5 | Medium | `repro_replay_diff.py --strict` still ignores witness identity fields such as outer envelope metadata and `turn_index`
   files: tools/repro_replay_diff.py
2. BUG-65 | original #7 | phase 5 | High | `repro_replay_diff.py` ignores sibling `turn_summary.md` input drift
   files: tools/repro_replay_diff.py
3. BUG-90 | original #10 | phase 5 | Medium | `repro_replay_diff.py` ignores cross-file `run.json.issue_id` drift in turn bundles
   files: tools/repro_replay_diff.py
4. BUG-104 | original #11 | phase 5 | Medium | `repro_replay_diff.py` ignores inner `payload.session_report.schema_version` drift in session bundles
   files: tools/repro_replay_diff.py
