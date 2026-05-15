# Window 10 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/artifact_roundtrip.py

- Delivery standard:
  - Nested child artifacts must participate in traversal and repair.
  - Process-level FAIL must never leave per-file PASS markers behind.
  - Direct-file repair support must match the advertised CLI contract.

1. BUG-79 | phase 6 | Medium | `tools/artifact_roundtrip.py` ignores nested `child_runs/**/*.json` when given a run directory
   files: tools/artifact_roundtrip.py
   mission: Traverse nested child_runs JSON files during roundtrip checks and repair. Treat nested artifacts as first-class billable evidence, not optional debris, so full-fidelity run bundles stay dependable.
   acceptance: artifact_roundtrip sees nested child_runs JSON files. | Directing the tool at a run directory covers nested artifacts end to end.
   nexus: Treat nested child_runs as first-class bundle members. | Use the same traversal rules in validation and fix modes.

2. BUG-94 | phase 6 | Medium | `artifact_roundtrip.py --strict` can report process-level `FAIL` while leaving changed files marked `PASS`
   files: tools/artifact_roundtrip.py
   mission: Align strict-mode process verdicts with per-file verdicts. A premium-quality strict report must read like a single coherent judgment, not a contradiction that forces human arbitration.
   acceptance: A strict FAIL leaves no contradictory PASS markers on changed files. | The emitted artifact clearly reflects the single final verdict.
   nexus: Do not let a process-level FAIL coexist with lingering PASS markers on changed files. | Keep strict-mode reporting internally consistent.

