# Window 04 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - xyzgl/orchestrator/session_loop.py
  - xyzgl/orchestrator/tutor_phases.py

- Delivery standard:
  - Carry forward the real conversational state that drove the tutor.
  - Keep exported artifacts consistent with the runtime path.
  - Regression tests should span at least two turns.

1. BUG-09 | phase 3 | Medium | Session orchestration loses conversational continuity across turns
   files: xyzgl/orchestrator/session_loop.py, xyzgl/orchestrator/tutor_phases.py
   mission: Preserve conversational continuity across turns in the session orchestrator. Make the continuity explicit enough that longitudinal tutoring features and customer-facing session exports can be trusted as a product surface, not just a debug trace.
   acceptance: Multi-turn tests retain the expected prior-turn context. | Exported session artifacts describe the same continuity the runtime used.
   nexus: Carry forward the learner context and tutor state that the next turn depends on. | Keep exported artifacts aligned with the actual turn-to-turn state.

