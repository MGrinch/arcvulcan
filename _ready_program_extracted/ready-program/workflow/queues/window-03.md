# Window 03 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - xyzgl/grounding/retrieval.py
  - tools/retrieval_eval_bench.py
  - xyzgl/grounding/corpus.py

- Delivery standard:
  - Shown evidence must contain the actual matched content.
  - Malformed benchmark rows must fail early with useful diagnostics.
  - Chunking changes must preserve deterministic retrieval behavior.

1. BUG-70 | phase 2 | Medium | Hard no-overlap chunk splitting breaks retrieval at passage boundaries
   files: xyzgl/grounding/corpus.py
   mission: Repair chunk boundary logic so evidence at passage edges remains retrievable. Preserve deterministic chunk identities so benchmark baselines and paid evaluation packs do not churn after the fix.
   acceptance: Retrieval succeeds for boundary-spanning evidence that previously disappeared. | Chunking remains deterministic for the same corpus and config.
   nexus: Soften no-overlap splitting enough to preserve boundary evidence. | Keep chunk identity deterministic after the change.

2. BUG-93 | phase 2 | High | Retrieval and evaluation can certify snippets whose shown excerpt omits the actual matching evidence
   files: tools/retrieval_eval_bench.py, xyzgl/grounding/retrieval.py
   mission: Make shown retrieval excerpts contain the actual matched evidence. The displayed snippet should be support-grade proof that can be shown to a customer or reviewer without a second forensic lookup.
   acceptance: Certified snippets show the text that justified the match. | Evaluation cannot green-light an excerpt that hides the evidence.
   nexus: Bind displayed excerpt generation to the real matching span. | Prevent certification when the displayed excerpt omits the proof.

3. BUG-99 | phase 6 | High | `retrieval_eval_bench.py` does not validate benchmark-case field types and can false-pass or crash on malformed rows
   files: tools/retrieval_eval_bench.py
   mission: Validate benchmark row field types before retrieval evaluation trusts them. Replace late crashes and false passes with crisp contract failures that make external benchmark packs safe to sell, share, and automate.
   acceptance: Malformed benchmark rows produce clear validation failures. | Evaluation no longer falsely passes because of implicit coercion.
   nexus: Fail early on malformed benchmark row types. | Keep malformed rows from false-passing or crashing late.

