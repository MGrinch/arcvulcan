# Active Queue: Window 11

- Name: Detectors, Scanners, and Drift Radar
- Area: Owns secret scanning, protocol drift, graph invariants, mirror leakage, and related detector bugs.
- Archived source queue: `queues/window-11.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 11
- Remaining items: 4

1. BUG-130 | original #4 | phase 6 | Medium | `node_evolution_diff.py` ignores the canonical `turns[*].eval.next_action` field when linking close turns
   files: tools/node_evolution_diff.py
2. BUG-26 | original #9 | phase 6 | Medium | `protocol_drift_radar.py` has a tail-position blind spot after 4,000 characters
   files: tools/protocol_drift_radar.py
3. BUG-64 | original #10 | phase 6 | High | `tools/secret_scanner.py` silently skips large text files
   files: tools/secret_scanner.py
4. BUG-73 | original #13 | phase 6 | Medium | `protocol_drift_radar.py` ignores `session_summary.md` in directory scans
   files: tools/protocol_drift_radar.py
