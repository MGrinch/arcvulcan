# Window 15 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/harness_lattice.py
  - tools/lattice_lib.py
  - tools/redteam_rag_poisoning_suite.py
  - tools/mirror_calibration_bench.py

- Delivery standard:
  - False-green benchmark passes are worse than explicit failures.
  - Boundary checks must reject malformed structured layouts.
  - Bench outputs should prove behavior changed for the tested dimension.

1. BUG-96 | phase 6 | Medium | `harness_lattice.py` is a false-green sensitivity sweep that never checks whether lattice dimensions change the reply meaningfully
   files: tools/harness_lattice.py, tools/lattice_lib.py
   mission: Require harness_lattice to prove meaningful semantic movement across lattice dimensions. Turn the suite into a decision-grade benchmark that can justify tuning, procurement, and premium quality claims.
   acceptance: A false-green sweep with identical meanings now fails or warns explicitly. | Reported lattice findings demonstrate real semantic change.
   nexus: Measure whether dimension changes alter reply meaningfully, not only mechanically. | Fail closed when the sweep produces no substantive behavioral delta.

2. BUG-98 | phase 6 | High | `redteam_rag_poisoning_suite.py` boundary checks accept malformed structured prompt layouts as PASS
   files: tools/redteam_rag_poisoning_suite.py
   mission: Reject malformed structured prompt layouts in the RAG poisoning boundary suite. The boundary suite should behave like a hard security product, not a permissive demo that rewards malformed attack inputs with PASS.
   acceptance: Malformed structured prompt layouts are rejected or reported as failures. | PASS is reserved for genuinely valid boundary cases.
   nexus: Tighten boundary-check input validation before PASS evaluation. | Make malformed structured layouts fail closed instead of falling through as acceptable.

