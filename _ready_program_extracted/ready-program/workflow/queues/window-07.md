# Window 07 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/repro_replay_diff.py

- Delivery standard:
  - Bundle diffing must detect nested metadata drift.
  - A green replay result must mean semantic parity, not superficial filename parity.
  - Tests should include mutated inner fields.

1. BUG-90 | phase 5 | Medium | `repro_replay_diff.py` ignores cross-file `run.json.issue_id` drift in turn bundles
   files: tools/repro_replay_diff.py
   mission: Catch run.json issue_id drift across files inside replay bundles. Replay verdicts should be strong enough that teams can trust a green status in paid support and regression review workflows.
   acceptance: Replay diff flags mismatched issue ids anywhere in the bundle. | A green result requires cross-file identity parity.
   nexus: Compare cross-file issue identity, not only local file content. | Keep bundle validation strict across nested artifacts.

2. BUG-104 | phase 5 | Medium | `repro_replay_diff.py` ignores inner `payload.session_report.schema_version` drift in session bundles
   files: tools/repro_replay_diff.py
   mission: Catch schema-version drift hidden inside session bundle payloads. Make semantic drift visible early so bundle consumers and downstream integrations do not discover incompatibilities after shipment.
   acceptance: Replay diff flags inner schema_version drift. | Nested payload metadata participates in semantic diffing.
   nexus: Inspect inner payload.session_report.schema_version values. | Do not stop at top-level file naming parity.

