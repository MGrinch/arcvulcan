# Active Queue: Window 04

- Name: Tutor Runtime and Session Logic
- Area: Owns tutor phases, session loop semantics, learner-state continuity, CLI resume, and policy-close behavior.
- Archived source queue: `queues/window-04.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 3

1. BUG-129 | original #3 | phase 4 | High | `run_session()` can execute up to 256 turns while `SessionReport.turns` silently stops recording after 128
   files: xyzgl/orchestrator/session_loop.py
2. BUG-07 | original #7 | phase 3 | High | Session loop has no terminal condition after full mastery
   files: tools/harness_session.py, xyzgl/orchestrator/session_loop.py
3. BUG-09 | original #9 | phase 3 | Medium | Session orchestration loses conversational continuity across turns
   files: xyzgl/orchestrator/session_loop.py, xyzgl/orchestrator/tutor_phases.py
