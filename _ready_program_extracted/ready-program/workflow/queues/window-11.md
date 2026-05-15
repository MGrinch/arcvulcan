# Window 11 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/prompt_snapshot_guard.py
  - tools/grounding_injection_audit.py
  - tools/doc_code_link_checker.py
  - documentation/tools/

- Delivery standard:
  - Guard tools must reject malformed or missing support assets before claiming success.
  - Docs and code must move together.
  - Environment sensitivity should be isolated behind explicit gates or fixtures.

1. BUG-42 | phase 6 | High | `grounding_injection_audit.py` is environment-sensitive and can misattribute failures
   files: tools/grounding_injection_audit.py
   mission: Make grounding injection audit results stable across environments. Deterministic audit behavior is what turns the tool from an internal helper into a credible customer-facing assurance check.
   acceptance: The same test case yields the same verdict across supported environments. | Failure messages point at the actual cause rather than setup variance.
   nexus: Isolate environment-dependent factors behind explicit setup or fixtures. | Keep failure attribution tied to the real grounding defect, not host noise.

2. BUG-53 | phase 6 | Medium | `tools/signal_fidelity_port.py` is missing required companion docs
   files: documentation/tools/ai_, documentation/tools/ai_signal_fidelity_port.md, documentation/tools/ai_signal_fidelity_port.txt, tools/doc_code_link_checker.py, tools/signal_fidelity_port.py
   mission: Ship the required companion docs alongside signal_fidelity_port. Treat the docs as part of the sellable feature so operators can adopt the tool without reading source or reverse-engineering hidden assumptions.
   acceptance: Required companion docs exist and pass doc-code link checks. | Tool-facing docs describe the real shipped behavior.
   nexus: Add or regenerate the missing doc artifacts and wire doc-code checks to them. | Keep tool help, docs, and doc-link checks in sync.

3. BUG-77 | phase 6 | Low | `tools/apply_signal_fidelity_overlay.py` defaults to an overlay archive that is not actually shipped
   files: documentation/tools/ai_apply_signal_fidelity_overlay.md, tools/apply_signal_fidelity_overlay.py
   mission: Stop defaulting to an overlay archive that the repo does not ship. A first-run experience that works out of the box is critical if the tool is going to feel productized rather than hand-held.
   acceptance: Default execution works without referencing a nonexistent overlay archive. | Documentation matches the actual default path.
   nexus: Point defaults at a shipped asset or require explicit input. | Make docs and CLI help reflect the real default behavior.

