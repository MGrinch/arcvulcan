# Active Queue: Window 09

- Name: Artifact Schemas and CI Gates
- Area: Owns canonical artifacts, schema validation, CI outputs, and run-bundle plumbing bugs.
- Archived source queue: `queues/window-09.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 6

1. BUG-134 | original #3 | phase 6 | Medium | `artifact_roundtrip.py --fix` cannot rewrite a supported direct JSON file target unless it lives under the repo `runs/` root
   files: tools/artifact_roundtrip.py
2. BUG-112 | original #7 | phase 6 | Medium | `validate_schemas.py` has incomplete shipped-schema coverage in both direct-file and run-directory validation modes
   files: schemas/prompt_snapshots.schema.json, tools/validate_schemas.py
3. BUG-113 | original #8 | phase 6 | Medium | Repro smoke tools emit other tools' report names and schema versions, and `validate_schemas.py` blesses the mismatch as canonical
   files: tools/repro_backends_smoke.py, tools/repro_grounding_protocol_smoke.py, tools/validate_schemas.py
4. BUG-76 | original #9 | phase 6 | Medium | `tools/ci_gate.py` sanitizes child stdout before extracting the session run dir, so it cannot locate the run bundle it just created
   files: tools/ci_gate.py
5. BUG-79 | original #11 | phase 6 | Medium | `tools/artifact_roundtrip.py` ignores nested `child_runs/**/*.json` when given a run directory
   files: tools/artifact_roundtrip.py
6. BUG-94 | original #13 | phase 6 | Medium | `artifact_roundtrip.py --strict` can report process-level `FAIL` while leaving changed files marked `PASS`
   files: tools/artifact_roundtrip.py
