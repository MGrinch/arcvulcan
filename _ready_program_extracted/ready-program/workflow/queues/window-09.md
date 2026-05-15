# Window 09 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/validate_schemas.py
  - tools/ci_gate.py
  - tools/coverage_gate.py
  - tools/repro_backends_smoke.py

- Delivery standard:
  - If an artifact is emitted, it must be declared and schema-correct.
  - CI must fail for real secret or scaffold issues, not report the wrong cause.
  - Smoke reports must never impersonate another tool's schema.

1. BUG-113 | phase 6 | Medium | Repro smoke tools emit other tools' report names and schema versions, and `validate_schemas.py` blesses the mismatch as canonical
   files: tools/repro_backends_smoke.py, tools/repro_grounding_protocol_smoke.py, tools/validate_schemas.py
   mission: Stop smoke tools from impersonating other tools' report names or schema identities. Every emitted report should be reliable enough to feed billing, compliance, and support pipelines without manual relabeling.
   acceptance: Smoke artifacts carry their own canonical name and schema. | Schema validation rejects mismatched tool identities.
   nexus: Bind report filenames and schema_version fields to the emitting tool. | Teach validate_schemas to reject cross-tool identity mismatches.

2. BUG-76 | phase 6 | Medium | `tools/ci_gate.py` sanitizes child stdout before extracting the session run dir, so it cannot locate the run bundle it just created
   files: tools/ci_gate.py
   mission: Keep ci_gate from losing the child run directory it just created. The fix should make CI failures self-serve, so a paying team can inspect the exact bundle without reproducing the job.
   acceptance: ci_gate can locate its created run bundle after sanitization. | The fix does not reintroduce unsafe child-output handling.
   nexus: Extract run directory before any stdout sanitization step. | Keep ci_gate's run-bundle lookup tied to the actual child output.

