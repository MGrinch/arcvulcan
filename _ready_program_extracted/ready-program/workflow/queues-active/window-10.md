# Active Queue: Window 10

- Name: Workflow Companion and Audit Guards
- Area: Owns prompt snapshots, citation guards, signal-fidelity tools, doc-code workflow tooling, and audit guardrails.
- Archived source queue: `queues/window-10.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 6

1. BUG-126 | original #3 | phase 6 | Medium | `prompt_snapshot_guard.py` does not actually snapshot a no-protocol prompt for its canonical `no_protocol_no_grounding` case
   files: tools/prompt_snapshot_guard.py, xyzgl/protocols.py
2. BUG-41 | original #7 | phase 6 | High | `latency_cost_budget_enforcer.py` is not hermetic
   files: tools/latency_cost_budget_enforcer.py
3. BUG-42 | original #8 | phase 6 | High | `grounding_injection_audit.py` is environment-sensitive and can misattribute failures
   files: tools/grounding_injection_audit.py
4. BUG-53 | original #9 | phase 6 | Medium | `tools/signal_fidelity_port.py` is missing required companion docs
   files: documentation/tools/ai_, documentation/tools/ai_signal_fidelity_port.md, documentation/tools/ai_signal_fidelity_port.txt, tools/doc_code_link_checker.py, tools/signal_fidelity_port.py
5. BUG-77 | original #10 | phase 6 | Low | `tools/apply_signal_fidelity_overlay.py` defaults to an overlay archive that is not actually shipped
   files: documentation/tools/ai_apply_signal_fidelity_overlay.md, tools/apply_signal_fidelity_overlay.py
6. BUG-96 | original #11 | phase 6 | Medium | `harness_lattice.py` is a false-green sensitivity sweep that never checks whether lattice dimensions change the reply meaningfully
   files: tools/harness_lattice.py, tools/lattice_lib.py
