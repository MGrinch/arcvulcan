# Active Queue: Window 05

- Name: Harness Turn and Artifact Integrity
- Area: Owns harness_turn behavior, turn artifacts, witness event identity, and turn-facing run path bugs.
- Archived source queue: `queues/window-05.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 3

1. BUG-23 | original #3 | phase 4 | High | Turn artifacts do not faithfully record the model-facing input
   files: tools/harness_turn.py, xyzgl/prompting.py, xyzgl/router.py
2. BUG-86 | original #7 | phase 4 | Medium | `harness_turn.py` can emit unstable `event_id` values for semantically identical deterministic runs
   files: tools/harness_turn.py, witness/core.py
3. BUG-62 | original #9 | phase 4 | Medium | `harness_turn.py` artifacts are not self-describing for env-only backend-error exposure and fault-injection runs
   files: tools/harness_turn.py, xyzgl/backends/fault.py, xyzgl/router.py
