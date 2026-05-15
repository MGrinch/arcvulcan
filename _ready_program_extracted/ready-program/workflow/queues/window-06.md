# Window 06 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/harness_session.py
  - tools/seed_sweep.py
  - tools/run_paths.py
  - xyzgl/orchestrator/session_loop.py

- Delivery standard:
  - Run identity must reflect the real workload, not a brittle placeholder.
  - Privacy and mirror controls must propagate through all tooling layers.
  - Artifacts must tell the truth about the learner state that actually drove tutoring.

1. BUG-50 | phase 4 | High | Mirror enablement and privacy controls are not propagated or auditable across session tooling
   files: tools/harness_session.py, tools/seed_sweep.py, xyzgl/orchestrator/mirror.py
   mission: Propagate mirror enablement and privacy controls through every session tool and artifact. Treat those controls as billable trust features whose effective state must stay inspectable from CLI to final export.
   acceptance: Mirror/privacy settings survive tool-to-tool handoff. | Artifacts show the effective mirror/privacy state that drove execution.
   nexus: Push mirror/privacy flags through harness_session, seed_sweep, and runtime plumbing. | Record those controls in exported artifacts so auditors can verify them.

2. BUG-52 | phase 4 | Medium | `seed_sweep.py` run identity is predictably tied to `--seed`, not to the actual sweep workload
   files: tools/run_paths.py, tools/seed_sweep.py
   mission: Make sweep run identity depend on the actual workload, not only the seed integer. Stable but truthful run identity makes comparison dashboards, customer reports, and support escalations materially more useful.
   acceptance: Changing workload with the same seed changes run identity appropriately. | Re-running the same workload and seed keeps the same identity.
   nexus: Derive run identity from workload shape as well as seed. | Keep deterministic replay stable for the same workload.

3. BUG-55 | phase 4 | Medium | `run_paths.py` resolves default and relative runs roots against the caller's current working directory
   files: tools/harness_session.py, tools/run_paths.py, tools/runs/, tools/seed_sweep.py
   mission: Resolve runs roots against the tool contract instead of the caller's cwd. That path contract should be reliable enough for scheduled jobs, CI runners, and customer-hosted automation to use without wrapper scripts.
   acceptance: The same command resolves the same run root from different cwd values. | Harness and sweep tools agree on where runs live.
   nexus: Anchor default and relative run roots to a stable base path. | Keep tooling behavior portable across invocation contexts.

4. BUG-82 | phase 3 | Medium | Session artifacts misreport the learner state that actually drove tutoring, and the `flow` vs `frustrated` stub-tutor branch is behaviorally dead in exported output
   files: tools/harness_session.py, xyzgl/orchestrator/session_loop.py
   mission: Tell the truth about the learner state and active tutoring branch in session artifacts. The exported narrative should be accurate enough to power premium analytics, instructor review, and customer success triage.
   acceptance: Session artifacts report the real learner state and branch taken. | The flow vs frustrated branch is either exercised truthfully or no longer falsely implied.
   nexus: Export the learner state that actually drove tutoring. | Revive or remove dead stub-tutor branches so artifacts cannot claim nonexistent behavior.

