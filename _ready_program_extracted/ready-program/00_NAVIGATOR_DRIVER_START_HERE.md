# 00_NAVIGATOR_DRIVER_START_HERE.md

> Name: ArcVulcan (formerly Project Daedalus / XYZGL; see `README.md` for full name history).
Project name: ArcVulcan

If you're opening this repo fresh:

1. Run the basic health check:
```bash
python tools/doctor.py
```

2. Run the single-turn harness:
```bash
python tools/harness_turn.py --issue ISSUE-20260129-001
```

3. Optional: run the lattice harness to sanity-check stability across a grid:
```bash
python tools/harness_lattice.py --issue ISSUE-20260129-002
```

4. Validate JSON outputs:
```bash
python tools/validate_schemas.py runs/<run_id>/
```

5. Skim docs in this order:
- `NORTH_STAR.md`
- `STABLE/WORKFLOW_ASSISTANT.md`
- `STABLE/ROLE_PROTOCOL.md`
- `STABLE/WITNESS_PROTOCOL_v2.1.md`
- `STABLE/SPEC_v3.0.2.md`
- `documentation/tools/ai_debug_harness_turn.txt`
- `documentation/tools/ai_debug_harness_lattice.txt`
- `documentation/tools/ai_validate_schemas.txt`
- `documentation/protocols/ai_role_protocol.txt`
- `documentation/grounding/ai_grounding.txt`

6. Then explore:
- `xyzgl/router.py`
- `xyzgl/backends/registry.py`
- `xyzgl/backends/gemini.py`
- `xyzgl/backends/ollama.py`
- `xyzgl/welding_tutor.py`
- `witness/core.py`

7. Configure real backends if needed:
- `documentation/backends/ai_backends.txt`

## Optional Developer Dependencies

ArcVulcan is runnable in a clean Python environment. A few advanced paths are optional:

- Signal Fidelity Overlay
  - Tool: `python tools/apply_signal_fidelity_overlay.py --issue ISSUE-...`
  - If you supply a `.rar` overlay yourself, you need an external extractor such as `7z`.
  - To avoid external tools, pass `--overlay path/to/overlay.zip` or `--overlay path/to/dir/`.
- Coverage-guided fuzzing
  - Tool: `python tools/atheris_fuzz_router.py --issue ISSUE-... --seconds 10`
  - Better coverage comes from `pip install atheris`; otherwise a deterministic fallback fuzzer is used.
- Deep mutation testing
  - The built-in mutation check works out of the box.
  - For a real engine: `pip install cosmic-ray` then run `python tools/mutation_suite.py --engine cosmic-ray ...`

These are intentionally not hard dependencies because they add weight to the default install.
