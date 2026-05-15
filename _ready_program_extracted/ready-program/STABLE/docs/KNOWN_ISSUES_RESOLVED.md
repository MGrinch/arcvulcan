# KNOWN_ISSUES_RESOLVED.md (STABLE)
Recent resolved issues retained in this cleaned snapshot.

- ISSUE-20260201-009
  - Symptom:
    - `tools/targeted_sweep.py` writes `dummy_overlay.zip` but does not declare it in `run.json.outputs`, breaking run-bundle integrity.
  - Repro:
    - `python tools/targeted_sweep.py --issue ISSUE-20260201-009`
    - Inspect `runs/<run_id>/run.json` vs files in the run directory.
  - Expected:
    - All artifacts created by the tool are declared in `run.json.outputs`.
  - Actual:
    - `dummy_overlay.zip` existed but was missing from `run.json.outputs`.
  - Fix Plan:
    - Add `dummy_overlay.zip` to the `outputs` list.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-011
  - Symptom:
    - `tools/run_paths.py` does not set bytecode guards, so importing it can create `tools/__pycache__/run_paths.*.pyc` in normal environments.
  - Repro:
    - In a clean repo: `python -c "import tools.run_paths"`
    - Observe `tools/__pycache__/` contents.
  - Expected:
    - Tools should default to `PYTHONDONTWRITEBYTECODE=1` / `sys.dont_write_bytecode=True`.
  - Actual:
    - Importing `run_paths` could generate bytecode artifacts.
  - Fix Plan:
    - Set `PYTHONDONTWRITEBYTECODE` and `sys.dont_write_bytecode` in `run_paths.py` at import time.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-014
  - Symptom:
    - `mirror_calibration_bench` and `mirror_leakage_detector` did not emit `*_summary.md`, unlike the standard tool contract.
  - Repro:
    - `python tools/mirror_leakage_detector.py --issue ISSUE-20260201-014 runs/<session_run_dir>/session_report.json`
    - `python tools/mirror_calibration_bench.py --issue ISSUE-20260201-014 runs/<session_run_dir>/session_report.json`
  - Expected:
    - Each tool emits `{tool}_report.json`, `{tool}_summary.md`, and `run.json`, and declares them in `run.json.outputs`.
  - Actual:
    - Summary markdown was missing and not declared.
  - Fix Plan:
    - Write a short summary markdown in all exit paths and include it in outputs.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-006
  - Symptom:
    - `tools/selfcheck.py.bak` backup file existed in-repo and was not detected by `doctor.py`.
  - Repro:
    - `ls tools/selfcheck.py.bak`
  - Fix:
    - Removed the backup artifact.
    - Added a `doctor.py` warning rule for common backup artifacts (`*.bak`, `*~`).
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-013
  - Symptom:
    - `mutation_suite` leaked child oracle (`selfcheck.py`) output to stdout (misleading "FAIL:" lines) even when overall PASS.
  - Repro:
    - `python tools/mutation_suite.py --issue ISSUE-20260201-013`
  - Fix:
    - Capture oracle stdout/stderr per mutant and attach a tail to `mutation_report.json` instead of printing.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-015
  - Symptom:
    - `doctor.py` printed a PASS header and exited 0 even when repo was not distribution-clean (warnings).
  - Repro:
    - Create a cache artifact (e.g., `tools/__pycache__/`), then run `python tools/doctor.py`.
  - Fix:
    - Default behavior is now strict: warnings -> `INCOMPLETE` and exit code 2.
    - Added `--lenient` to keep the legacy "PASS+WARN" behavior.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-018
  - Symptom:
    - Many tools did not validate `--issue` format and would write schema-invalid run bundles.
  - Repro:
    - `python tools/harness_turn.py --issue ISSUE-20260201-TEST --text x`
  - Fix:
    - Adopted `validate_issue_id()` across the primary toolchain (harnesses, scanners, gates, and analyzers) and fail fast with exit code 2.
  - Status: RESOLVED (2026-02-01)

- ISSUE-20260201-019
  - Symptom:
    - Some tools created empty `runs/<run_id>/` directories on early FAIL/INCOMPLETE (no `run.json`, no report), breaking audit trails.
  - Repro:
    - `python tools/mirror_calibration_bench.py --issue ISSUE-20260201-019 /tmp/daedalus_empty_run`
  - Fix:
    - Standardized "validate first, allocate later" in tools that previously allocated the run dir before input validation/discovery.
    - Affected tools: `protocol_drift_radar`, `mirror_calibration_bench`, `mirror_leakage_detector`, `node_evolution_diff`, `artifact_roundtrip`.
  - Status: RESOLVED (2026-02-01)
