# Active Queue: Window 13

- Name: Fuzzers, Benches, and Redteam
- Area: Owns fuzzers, calibration benches, sensitivity sweeps, and redteam suite bugs.
- Archived source queue: `queues/window-13.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 4
- Remaining items: 9

1. BUG-125 | original #3 | phase 6 | Medium | `atheris_fuzz_router.py` reports `PASS` even when Atheris never ran and the tool silently downgraded to the fallback loop
   files: tools/atheris_fuzz_router.py
2. BUG-101 | original #5 | phase 6 | Medium | Multiple standalone tools accept semantically invalid CLI parameters and then coerce, crash, or emit internally inconsistent artifacts
   files: tools/atheris_fuzz_router.py, tools/mirror_calibration_bench.py, tools/mutation_suite.py, tools/seed_sweep.py
3. BUG-34 | original #7 | phase 6 | Medium | `property_turn_fuzzer.py` writes non-canonical `run.json`
   files: tools/property_turn_fuzzer.py
4. BUG-35 | original #8 | phase 6 | Medium | Turn fuzzer cannot reach the welding-specific single-turn branch
   files: tools/property_turn_fuzzer.py, xyzgl/router.py
5. BUG-36 | original #9 | phase 6 | Medium | Turn fuzzer cannot generate known control and Unicode stressors
   files: tools/property_turn_fuzzer.py
6. BUG-44 | original #10 | phase 6 | Medium | `property_turn_fuzzer.py` truncates evidence and changes schema on incomplete path
   files: tools/property_turn_fuzzer.py
7. BUG-63 | original #11 | phase 6 | Low | `ai_property_turn_fuzzer.md` is out of sync with actual tool outputs
   files: documentation/tools/ai_property_turn_fuzzer.md, tools/property_turn_fuzzer.py
8. BUG-68 | original #12 | phase 6 | Medium | `property_turn_fuzzer.py` overstates coverage when `--max-len=0`
   files: tools/property_turn_fuzzer.py
9. BUG-98 | original #13 | phase 6 | High | `redteam_rag_poisoning_suite.py` boundary checks accept malformed structured prompt layouts as PASS
   files: tools/redteam_rag_poisoning_suite.py
