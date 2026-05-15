# Active Queue: Window 08

- Name: Sweep, Verifier, and Run-Path Orchestration
- Area: Owns targeted sweep handoff, cadence verification, run-path orchestration, and repo-safety workflow bugs.
- Archived source queue: `queues/window-08.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 5
- Remaining items: 4

1. BUG-127 | original #3 | phase 6 | Medium | Several tools hard-code `run.json.deterministic` in ways that do not match their real run identity or replay semantics
   files: tools/atheris_fuzz_router.py, tools/coverage_gate.py, tools/harness_session.py, tools/stage_timing_profiler.py, tools/targeted_sweep.py
2. BUG-31 | original #7 | phase 5 | Medium | `targeted_sweep.py` does not forward `--allow-external-path` to child tools
   files: tools/run_paths.py, tools/targeted_sweep.py
3. BUG-45 | original #8 | phase 5 | Medium | `targeted_sweep.py` sanitizes child output before extracting run paths
   files: tools/targeted_sweep.py
4. BUG-67 | original #9 | phase 5 | High | `targeted_sweep.py` contaminates the repo before running `doctor`
   files: tools/doctor.py, tools/targeted_sweep.py
