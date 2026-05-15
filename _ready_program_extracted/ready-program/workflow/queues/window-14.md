# Window 14 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/property_turn_fuzzer.py
  - tools/atheris_fuzz_router.py
  - xyzgl/router.py

- Delivery standard:
  - Run bundles must remain canonical even on incomplete or failing paths.
  - Coverage metrics must correspond to the true exercised branch space.
  - Counterexamples and failing payloads must survive export.

1. BUG-34 | phase 6 | Medium | `property_turn_fuzzer.py` writes non-canonical `run.json`
   files: tools/property_turn_fuzzer.py
   mission: Make property_turn_fuzzer emit canonical run.json artifacts. The emitted bundle should be production-grade evidence that can flow through the same tooling, dashboards, and paid assurance workflows as any other run.
   acceptance: Fuzzer run.json matches canonical schema and field expectations. | Roundtrip or schema validation accepts the emitted bundle without fix-up.
   nexus: Align the fuzzer's bundle writer with canonical run.json expectations. | Keep incomplete or failing paths canonical as well.

2. BUG-35 | phase 6 | Medium | Turn fuzzer cannot reach the welding-specific single-turn branch
   files: tools/property_turn_fuzzer.py, xyzgl/router.py
   mission: Reach the welding-specific single-turn branch from the turn fuzzer. Create proof that the domain-critical branch is truly exercised, so the coverage story maps to the product customers are buying.
   acceptance: Fuzzer coverage includes the welding-specific single-turn branch. | Artifacts prove the targeted branch was exercised.
   nexus: Generate inputs that can actually drive the welding-specific branch. | Keep the route selection explicit in the produced evidence.

3. BUG-36 | phase 6 | Medium | Turn fuzzer cannot generate known control and Unicode stressors
   files: tools/property_turn_fuzzer.py
   mission: Generate the known control and Unicode stressors that the fuzzer currently misses. This should harden the tutor for messy real-world inputs that show up in international and enterprise deployments.
   acceptance: The fuzzer now emits the targeted control and Unicode stressors. | Generated evidence remains replayable and deterministic.
   nexus: Expand case generation to cover control and Unicode edge inputs. | Preserve determinism for the same seed and generator config.

4. BUG-44 | phase 6 | Medium | `property_turn_fuzzer.py` truncates evidence and changes schema on incomplete path
   files: tools/property_turn_fuzzer.py
   mission: Keep evidence and schema canonical even on incomplete fuzzer paths. Failed paths should still produce support-ready artifacts that accelerate debugging instead of becoming expensive dead ends.
   acceptance: Incomplete fuzzer paths still emit canonical schema. | Exported evidence retains the information needed to reproduce the failure.
   nexus: Do not truncate away the failing evidence needed for replay. | Preserve canonical schema shape on incomplete execution.

5. BUG-63 | phase 6 | Low | `ai_property_turn_fuzzer.md` is out of sync with actual tool outputs
   files: documentation/tools/ai_property_turn_fuzzer.md, tools/property_turn_fuzzer.py
   mission: Bring ai_property_turn_fuzzer.md back into sync with real tool outputs. Make the documentation good enough to sell the feature and onboard a new operator without side-channel explanation.
   acceptance: The doc examples and field descriptions match the tool's actual outputs. | Doc-code drift tests or checks stay green.
   nexus: Update the docs to reflect the actual shipped output contract after the code fix. | Keep doc drift from reappearing by checking the real output surface.

6. BUG-68 | phase 6 | Medium | `property_turn_fuzzer.py` overstates coverage when `--max-len=0`
   files: tools/property_turn_fuzzer.py
   mission: Stop overstating coverage when max-len is zero. Honest coverage claims are part of the product's credibility, especially when the artifact may be shown to customers, auditors, or buyers.
   acceptance: Coverage claims for max-len=0 reflect the actual generated workload. | The tool no longer reports inflated coverage from a degenerate case.
   nexus: Treat max-len=0 as a distinct edge case with honest coverage reporting. | Do not let skipped generation masquerade as exercised space.

