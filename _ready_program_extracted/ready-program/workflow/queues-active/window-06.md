# Active Queue: Window 06

- Name: Session Harness and Determinism Plumbing
- Area: Owns harness_session, seed sweep, run path, determinism controls, and session-export auditability bugs.
- Archived source queue: `queues/window-06.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 6
- Remaining items: 6

1. BUG-12 | original #3 | phase 4 | Medium | Session harness does not exercise PROBE and simulated learner ignores context
   files: tools/harness_session.py
2. BUG-33 | original #6 | phase 4 | Medium | `harness_session` ignores env-backed protocol and grounding paths
   files: tools/harness_session.py
3. BUG-50 | original #8 | phase 4 | High | Mirror enablement and privacy controls are not propagated or auditable across session tooling
   files: tools/harness_session.py, tools/seed_sweep.py, xyzgl/orchestrator/mirror.py
4. BUG-52 | original #9 | phase 4 | Medium | `seed_sweep.py` run identity is predictably tied to `--seed`, not to the actual sweep workload
   files: tools/run_paths.py, tools/seed_sweep.py
5. BUG-55 | original #10 | phase 4 | Medium | `run_paths.py` resolves default and relative runs roots against the caller's current working directory
   files: tools/harness_session.py, tools/run_paths.py, tools/runs/, tools/seed_sweep.py
6. BUG-82 | original #11 | phase 3 | Medium | Session artifacts misreport the learner state that actually drove tutoring, and the `flow` vs `frustrated` stub-tutor branch is behaviorally dead in exported output
   files: tools/harness_session.py, xyzgl/orchestrator/session_loop.py
