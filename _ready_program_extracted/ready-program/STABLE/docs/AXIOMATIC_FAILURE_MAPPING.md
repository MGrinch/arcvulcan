# AXIOMATIC_FAILURE_MAPPING.md (STABLE)
Generated: 2026-02-06 (America/Toronto)

Maps each OPEN issue in `STABLE/docs/KNOWN_ISSUES.md` to invariants (axioms).

## Axioms
- **AX1** — Semantic determinism under --seed (stable semantic core).
- **AX2** — Audit trail mandatory (run bundle exists even on FAIL/INCOMPLETE).
- **AX3** — Artifact declaration integrity (run.json.outputs matches filesystem incl. nested child_runs).
- **AX4** — Canonical artifact formatting / strict roundtrip stability (with explicit vendor-raw exemptions).
- **AX5** — CLI contract & traceability (issue-id validation, exit codes, stdout contracts).
- **AX6** — Portability & privacy (no absolute paths; machine-specific data avoided).
- **AX7** — Repo hygiene (doctor stable; tools must not write __pycache__/junk into repo).
- **AX8** — Packaging extractability (stdlib-friendly; no external extractor required).
- **AX9** — Schema index coherence (schemas vs artifact_schemas consistent).
- **AX10** — Output size budgets bounded (reports scale safely).
- **AX11** — Tool semantic correctness (no dead/no-op logic causing wrong findings).

## Hotspots
- AX1: 19
- AX2: 35
- AX3: 7
- AX4: 6
- AX5: 40
- AX6: 20
- AX7: 6
- AX8: 1
- AX9: 1
- AX10: 21
- AX11: 75
## Map
- **ISSUE-20260206-001** — AX5, AX11
  - coverage thresholds accept nan/inf/-inf → bypass or force gate result.
- **ISSUE-20260206-002** — AX5, AX11
  - min-avg accepts nan/inf → PASS/FAIL can be forced at boundary.
- **ISSUE-20260206-003** — AX7, AX10, AX11
  - doctor reads full text files (md/txt) → OOM/hang at extreme sizes.
- **ISSUE-20260206-004** — AX2, AX11
  - prompt_snapshot_guard JSONDecodeError after run_dir alloc → empty bundle.
- **ISSUE-20260206-005** — AX7, AX11
  - mutation_suite writes in-place → hard-kill leaves repo mutated.

- **ISSUE-20260205-071** — AX2, AX10, AX11
  - subprocess.run capture_output without timeout → infinite hang / unbounded RAM.
- **ISSUE-20260205-072** — AX2, AX11
  - WitnessCore event-id JSON serialization can fail on non-JSON payload types → no event.
- **ISSUE-20260205-073** — AX5, AX11
  - property_turn_fuzzer negative cases → zero iterations → false PASS.
- **ISSUE-20260205-074** — AX5, AX11
  - seed_sweep reversed seed range → zero iterations → false PASS.
- **ISSUE-20260205-075** — AX11
  - util_http.post_json json.dumps TypeError not wrapped → inconsistent backend failure handling.
- **ISSUE-20260205-065** — AX5, AX10, AX11
  - harness_lattice cartesian product unbounded → combinatorial explosion / OOM risk.
- **ISSUE-20260205-064** — AX5, AX10, AX11
  - seed_sweep accepts extreme seed ranges → runaway runtime/memory; hammers backend.
- **ISSUE-20260205-063** — AX5, AX10, AX11
  - atheris_fuzz_router --seconds unbounded → MAX_INT seconds explodes work (fallback loop).
- **ISSUE-20260205-062** — AX2, AX11
  - reground_cadence_verifier can crash on non-int turn_index after allocating out_dir → empty bundle.
- **ISSUE-20260205-061** — AX2, AX11
  - doc_code_link_checker can crash on malformed AI_INDEX.json after allocating run_dir → empty bundle.
- **ISSUE-20260205-060** — AX10, AX11
  - multiple tools do unbounded json.loads(read_text()) → OOM/hang on huge artifacts; no max-bytes guard.
- **ISSUE-20260205-059** — AX2, AX11
  - issue_id.validate_issue_id does not strip newline; passes if caller strips but tool doesn't → audit mismatch.
- **ISSUE-20260205-058** — AX2
  - issue_id.validate_issue_id accepts whitespace-only issue ids (strip mismatch) → inconsistent validation across tools.
- **ISSUE-20260205-057** — AX2, AX11
  - protocol_drift_radar can crash on int(turn_index) cast after allocating run_dir → empty bundle.
- **ISSUE-20260205-056** — AX10, AX11
  - witness.core.scrub_pii recurses infinitely on cyclic objects → RecursionError under stress.
- **ISSUE-20260205-055** — AX10, AX11
  - mirror_calibration_bench uses SequenceMatcher on huge strings → quadratic slowdown / hang at extremes.
- **ISSUE-20260205-054** — AX11
  - router clamp uses slicing for n<0 → negative max_chars silently defeats size budget intent.
- **ISSUE-20260205-053** — AX2, AX11
  - mirror_leakage_detector crashes on decode/JSON/type errors after allocating run_dir → empty bundle.
- **ISSUE-20260205-052** — AX1, AX11
  - apply_signal_fidelity_overlay claims deterministic but uses wall-clock run_id / nondeterministic extractors.
- **ISSUE-20260205-051** — AX6, AX10, AX11
  - apply_signal_fidelity_overlay extracts zip with no size/ratio limits → zip bomb / disk exhaustion risk.
- **ISSUE-20260205-050** — AX10, AX11
  - curriculum_corpus_linter reads whole files with no max-bytes; special files can hang/OOM.
- **ISSUE-20260205-049** — AX2, AX11
  - secret_scanner stat() unguarded → PermissionError/OSError aborts scan and leaves empty bundle.
- **ISSUE-20260205-048** — AX1, AX2, AX7, AX11
  - prompt_snapshot_guard auto-writes baseline pre-report; read-only FS causes empty runs; determinism mislabeled.
- **ISSUE-20260205-047** — AX1, AX11
  - repro_replay_diff infers reground cadence (fallback 5) → replay divergence when original cadence differs.

- **ISSUE-20260205-046** — AX2, AX11
  - repro_replay_diff allocates out_dir before parsing JSON → empty run dir on parse/decode failures.
- **ISSUE-20260205-045** — AX6, AX11
  - run_paths write-probe can follow symlinks / TOCTOU in attacker-controlled runs dirs.
- **ISSUE-20260205-044** — AX2, AX11
  - graph_invariant_checker _load_json has no guard → empty run dir on bad encoding/JSON.
- **ISSUE-20260205-043** — AX2, AX11
  - graph_invariant_checker second-pass int() on last_verified_turn lacks try/except → crash.
- **ISSUE-20260205-042** — AX10, AX11
  - corpus chunker fails max_chars guarantee for oversized paragraphs → prompt bloat.
- **ISSUE-20260205-041** — AX3, AX10, AX11
  - protocol load unbounded (huge/special files) → hang/OOM before artifacts.
- **ISSUE-20260205-040** — AX2, AX11
  - ci_gate truncates stdout tail; loses run path; skips downstream validators.
- **ISSUE-20260205-039** — AX2, AX11
  - json_canon write_json non-atomic → torn JSON at disk/crash edges.

- **ISSUE-20260205-038** — AX2, AX11
  - Witness event_id can collide within same second for identical payload+issue.

- **ISSUE-20260205-037** — AX5, AX11
  - validate_issue_id checks format only; impossible dates / >999/day overflow accepted.

- **ISSUE-20260205-036** — AX2, AX11
  - reground_cadence_verifier can crash on decode/parse leaving empty run dir.

- **ISSUE-20260205-035** — AX11
  - time.time elapsed latency can go negative → budget tool can false-PASS.

- **ISSUE-20260205-034** — AX2, AX11
  - run_paths writable probe uses fixed filename; concurrency race scatters runs.

- **ISSUE-20260205-033** — AX2, AX3, AX11
  - run_id collisions possible (same ms + seeded random) → mixed/overwritten bundles.

- **ISSUE-20260205-032** — AX4, AX11
  - artifact_roundtrip claims NaN/Inf detection but stdlib JSON accepts them (false PASS).

- **ISSUE-20260205-031** — AX4, AX11
  - json_canon/witness allow NaN/Inf → non‑standard JSON artifacts.

- **ISSUE-20260205-030** — AX10, AX11
  - load_corpus reads/chunks huge sources upfront → OOM before budget applies.
- **ISSUE-20260205-029** — AX2, AX11
  - protocol load unreadable path not guarded → hard fail before artifacts.
- **ISSUE-20260205-028** — AX2, AX11
  - graph_invariant_checker crashes on non-int turn_index → empty run dir.
- **ISSUE-20260205-027** — AX11
  - graph_invariant_checker NaN confidence passes range check.
- **ISSUE-20260205-026** — AX2, AX10, AX11
  - scrub_pii lacks cycle detection → RecursionError / audit loss.
- **ISSUE-20260205-025** — AX6, AX10, AX11
  - DAEDALUS_GROUNDING_DIR resolve() escape → unintended file reads.
- **ISSUE-20260205-024** — AX2, AX10
  - capture_output buffers unbounded child output → OOM.
- **ISSUE-20260205-023** — AX2, AX11
  - No subprocess timeout → infinite hang (ci_gate/mutation/targeted_sweep/apply_overlay).
- **ISSUE-20260205-022** — AX2, AX11
  - NaN/Inf boundary poisoning across replays (oscillation).
- **ISSUE-20260205-021** — AX3, AX11
  - Infinite retry amplification under partial network failure.
- **ISSUE-20260205-020** — AX6, AX11
  - Symlink + zip overlay chain escape (filesystem semantics mismatch).
- **ISSUE-20260205-019** — AX10
  - Witness memory balloon at ~99.9% RAM (unbounded buffering).
- **ISSUE-20260205-018** — AX2, AX5
  - Partial-write artifacts misclassified as valid (torn JSON).
- **ISSUE-20260205-017** — AX11
  - Clock-skew replay divergence (time.time vs monotonic assumptions).
- **ISSUE-20260205-016** — AX8, AX11
  - Windows path-length overflow breaks replays (run id + nested dirs).

- **ISSUE-20260205-014** — AX10, AX11
  - `xyzgl/util_http.py` reads `resp.read()` unbounded, then `decode('utf-8')` and `json.loads(...)` (no streaming / max-bytes guard).
- **ISSUE-20260205-013** — AX6, AX10, AX11
  - `xyzgl/protocols.py` constructs `p = (repo_root / rel_path).resolve()` without enforcing that `p` stays under `repo_root` and then calls `p.read_text(...)` unbounded.
- **ISSUE-20260205-012** — AX6, AX11
  - It resolves `fpath = (gdir / rel_path).resolve()` and checks only `fpath.exists()`, without verifying `fpath` is within `gdir`.
- **ISSUE-20260205-011** — AX6, AX11
  - The scanner walks `root.rglob('*')`, uses `p.is_file()` and `p.read_text()` (both follow symlinks), and only uses the symlink’s in-repo name for reporting.
- **ISSUE-20260205-010** — AX11
  - Uses `t0 = time.time()` and `time.time() - t0` instead of `time.monotonic()` for elapsed time.
- **ISSUE-20260205-009** — AX5, AX11
  - It wraps `atheris.Fuzz()` in `try/except SystemExit: pass` and then unconditionally sets `pass=True` / `status='PASS'` and exits 0.
- **ISSUE-20260205-008** — AX6, AX11
  - Calls `ZipFile.extractall(tmp_dir)` without validating member paths; crafted zip entries like `../../pwned.txt` escape `tmp_dir`.

- **ISSUE-20260205-007** — AX2, AX11
  - invalid `manifest.json` JSON crashes `load_corpus()`; grounding-enabled `route_turn` (and harnesses) can hard-fail before writing run artifacts.
- **ISSUE-20260205-006** — AX6, AX11
  - grounding manifest `sources[].path` allows `..`/absolute path traversal; `load_corpus()` can read files outside the grounding directory (privacy/portability footgun).
- **ISSUE-20260205-005** — AX2, AX10
  - `witness.core.scrub_pii()` can raise `RecursionError` on extreme-depth payloads, preventing event creation/writes (audit loss at scale edges).
- **ISSUE-20260205-004** — AX2, AX11
  - `WitnessCore.make_event()` fails on non-JSON-serializable payload values (e.g., bytes), blocking report/event writing.
- **ISSUE-20260205-003** — AX2, AX11
  - `WitnessCore.write_event_json()` crashes on relative filenames (`event.json`) due to `os.makedirs('')` when no directory component is present.
- **ISSUE-20260205-002** — AX11
  - `util_http.post_json()` can raise uncaught `UnicodeDecodeError` on non-UTF8 responses (not wrapped as `HTTPError`).
- **ISSUE-20260205-001** — AX11
  - `util_http.post_json()` can raise uncaught `ValueError` for out-of-range timeouts (`timeout_s < 0`).

- **ISSUE-20260204-784** — AX5, AX11
  - grounding retrieval treats negative `max_snippets` / `max_chars` as Python-slice / negative-budget semantics (grounding balloons or disappears).
- **ISSUE-20260204-783** — AX2, AX5
  - `harness_session` can crash with `OSError: File name too long` when `--run-id` exceeds filesystem limits (no run bundle).
- **ISSUE-20260204-782** — AX5, AX6
  - `allocate_run_dir` allows `--run-id` path injection (absolute path overrides runs root; `..` escapes runs folder).
- **ISSUE-20260204-781** — AX2, AX5
  - `DAEDALUS_PROTOCOL_PATH` pointing to a directory crashes `route_turn` during protocol load, leaving an empty run dir in `harness_turn`.
- **ISSUE-20260204-780** — AX5, AX11
  - `latency_cost_budget_enforcer` returns PASS with `--cases 0` (no-op PASS: empty samples).
- **ISSUE-20260204-779** — AX5, AX11
  - `harness_session` returns PASS with `--max-turns 0` (no-op PASS: session has 0 turns).
- **ISSUE-20260204-778** — AX5, AX11
  - `seed_sweep` returns PASS when `--seed-start > --seed-end` (no-op PASS: empty samples).
- **ISSUE-20260204-777** — AX5, AX11
  - `property_turn_fuzzer` returns PASS with `--cases 0` (no-op PASS: no properties executed).
- **ISSUE-20260204-776** — AX2, AX5
  - `property_turn_fuzzer` crashes on `--max-len < 0` after allocating run dir, leaving an empty run bundle (audit gap).
- **ISSUE-20260204-775** — AX6, AX11
  - grounding chunking uses `split(\n\n)` and fails on CRLF blank lines (`\r\n\r\n`), producing oversized passages and causing grounding to exceed budgets / disappear on Windows depending on file line endings.
- **ISSUE-20260204-774** — AX5
  - run bundles appear to “disappear” or land in unexpected locations because default runs root is `cwd/runs` (depends on launch CWD).
- **ISSUE-20260202-716** — AX1
  - full-file determinism hashing fails even with fixed `--seed` because artifacts include time/latency fields.
- **ISSUE-20260202-714** — AX3
  - some tools create artifacts that are missing from `run.json.outputs` (often nested `child_runs/` or summary `.md`).
- **ISSUE-20260201-701** — AX7
  - `tools/targeted_sweep.py` can self-sabotage `doctor` by generating artifacts before running `doctor` (fails in a clean repo).
- **ISSUE-20260201-702** — AX2
  - several tools FAIL/INCOMPLETE on missing/invalid inputs without emitting any audit bundle (no run dir, no `run.json`).
- **ISSUE-20260201-703** — AX5
  - `tools/ci_gate.py` cannot locate the harness session run dir when `DAEDALUS_RUNS_DIR`’s folder name is not exactly `runs` or `daedalus_runs`.
- **ISSUE-20260202-717** — AX4
  - multiple tools write non-canonical `run.json` (not using `json_canon.write_json`), so `tools/artifact_roundtrip.py --strict` would rewrite it (strict FAIL).
- **ISSUE-20260202-916** — AX4
  - `tools/coverage_gate.py` produces vendor-raw `coverage_raw.json` (coverage.py JSON) that fails canonical strict roundtrip.
- **ISSUE-20260202-718** — AX5
  - `tools/repro_replay_diff.py` accepts `--issue` but does not validate `ISSUE-YYYYMMDD-NNN`.
- **ISSUE-20260202-719** — AX8
  - shipped Signal Fidelity overlay is `.rar` (not stdlib-friendly), so `apply_signal_fidelity_overlay` can be INCOMPLETE without an external extractor.
- **ISSUE-20260202-705** — AX10
  - `tools/harness_session.py` report size grows linearly with `--max-turns` (large JSON for long runs).
- **ISSUE-20260202-725** — AX5
  - many tools accept `--issue` but do not validate it (malformed IDs can enter run bundles).
- **ISSUE-20260202-726** — AX6
  - `session_report.json` records absolute `grounding_dir` paths (non-portable + can leak local filesystem layout).
- **ISSUE-20260202-727** — AX5
  - stdout “run dir” contract varies (`wrote outputs to <dir>` vs `(...wrote <dir>)`), breaking stdout-parsing meta-tools.
- **ISSUE-20260202-728** — AX9
  - `artifact_schemas/` is documented as an alias copy of `schemas/`, but it is only a partial subset (5 files vs 36).
- **ISSUE-20260202-729** — AX2
  - `tools/ontario_claims_citation_guard.py` can leave an **empty** run dir on early FAIL (allocates run dir, then exits without writing artifacts).
- **ISSUE-20260202-730** — AX7
  - `tools/artifact_roundtrip.py` bytecode guard is too late; running `python tools/artifact_roundtrip.py --help` can create `tools/__pycache__/` and fail `doctor`.
- **ISSUE-20260202-731** — AX3, AX4
  - `tools/artifact_roundtrip.py` only checks top-level `*.json` files when given a run directory and ignores nested run bundles under `child_runs/`.
- **ISSUE-20260202-732** — AX5
  - `tools/artifact_roundtrip.py` returns exit code 2 (INCOMPLETE) for invalid `--issue`, but its module docstring and run bundle metadata advertise only exit codes 0/1.
- **ISSUE-20260202-733** — AX3
  - `tools/validate_schemas.py` validates only a fixed set of filenames at the top level of a run directory and does not recurse into nested run bundles (e.g., `child_runs/`).
- **ISSUE-20260203-734** — AX6
  - `tools/artifact_roundtrip.py` report embeds absolute filesystem paths in `files[].file` and `path`, leaking local layout and breaking portability.
- **ISSUE-20260203-735** — AX11
  - `tools/secret_scanner.py` intends to allow obvious placeholders (`YOUR_API_KEY`, `<redacted>`), but the allowlist branch is a no-op (`pass`), so placeholders can still be flagged (false positives).
- **ISSUE-20260203-736** — AX1
  - `tools/secret_scanner.py` iterates files via `Path.rglob("*")` without sorting, so hit ordering can vary across filesystems/OS, weakening reproducibility of `secret_scan_report.json`.
- **ISSUE-20260203-737** — AX5
  - multiple tools document exit codes as only `0/1`, but return `2` (INCOMPLETE) for invalid issue IDs (confirmed: `secret_scanner`, `stage_timing_profiler`, `prompt_snapshot_guard`).
- **ISSUE-20260203-738** — AX1, AX5
  - `tools/ontario_claims_citation_guard.py` writes `deterministic: True` in `run.json` even though it generates a wall-clock run_id and embeds it in the report (byte-level outputs vary run-to-run).
- **ISSUE-20260203-739** — AX1, AX11
  - `tools/secret_scanner.py` stops after 50 hit-files, but file traversal is unsorted, so the *set* of reported hits can vary across OS/filesystems (not just ordering).
- **ISSUE-20260203-740** — AX6
  - `tools/prompt_snapshot_guard.py` writes an absolute `baseline_path` into `prompt_snapshot_report.json`, leaking local filesystem layout.
- **ISSUE-20260203-741** — AX11
  - `tools/ci_gate.py` runs `secret_scanner` without `--enforce`, so secrets can be detected in the report but CI still passes that step (exit code 0).
- **ISSUE-20260203-742** — AX6, AX1
  - `tools/grounding_injection_audit.py` writes `grounding_dir_abs` (resolved absolute path) into `grounding_audit_report.json`.
- **ISSUE-20260203-743** — AX6, AX1
  - `tools/curriculum_corpus_linter.py` stores a resolved absolute `grounding_dir` in `corpus_lint_report.json`.
- **ISSUE-20260203-744** — AX7, AX6
  - `tools/apply_signal_fidelity_overlay.py` writes overlay contents into repo-root `signal_fidelity_src/` (outside the run bundle) and records `out_root_abs` in the report.
- **ISSUE-20260203-745** — AX1, AX5
  - `tools/doc_code_link_checker.py` writes `deterministic: True` in `run.json` even though it generates a wall-clock `run_id` and embeds it in artifacts (byte-level outputs vary run-to-run).
- **ISSUE-20260203-746** — AX6
  - `tools/graph_invariant_checker.py` records the raw input `path` as `source` in `graph_invariant_report.json`; if invoked with an absolute path, it leaks local filesystem layout and breaks portability.
- **ISSUE-20260203-747** — AX6, AX1
  - multiple tools embed raw input paths (often absolute) in report fields like `source` or `target` while also claiming `deterministic: True` in `run.json` despite time-based `run_id` generation.
  - confirmed tools: `protocol_drift_radar`, `mirror_calibration_bench`, `mirror_leakage_detector`, `reground_cadence_verifier`, `repro_replay_diff`.
- **ISSUE-20260203-748** — AX1, AX5
  - `tools/ci_gate.py --seed X` does not propagate the seed to all sub-tools; some sub-runs silently use their default seed (often 1337).
- **ISSUE-20260203-749** — AX6
  - grounding stores verbatim excerpt text inside run artifacts (e.g., `prompt_meta.grounding.snippets[].excerpt`), so sharing run bundles can leak corpus content (copyright/proprietary text, internal SOPs, etc.).
- **ISSUE-20260203-750** — AX10
  - enabling grounding inflates `session_report.json` substantially because excerpts are duplicated (in `grounding_text` and in `prompt_meta.grounding.snippets[].excerpt`); report size scales with turns × snippet budget.
- **ISSUE-20260203-751** — AX2, AX6
  - `tools/retrieval_eval_bench.py` allocates a run dir, then returns INCOMPLETE early (missing/empty bench or empty corpus) without writing `run.json` / report artifacts, leaving an empty run directory (audit gap).
- **ISSUE-20260203-752** — AX5, AX7
  - `tools/run_paths.py` chooses `Path('runs')` relative to the current working directory (CWD). If you run tools from a subfolder (e.g., `cd tools`), run bundles land in `tools/runs/<run_id>` instead of the repo-root `runs/` (or `$DAEDALUS_RUNS_DIR`), contaminating the repo and breaking run-path assumptions.
- **ISSUE-20260203-753** — AX1, AX5
  - `tools/curriculum_corpus_linter.py` writes `deterministic: True` in `run.json`, but its `run_id` is wall-clock based (and written into `corpus_lint_report.json`), so byte-level outputs vary run-to-run even with the same `--seed`.
- **ISSUE-20260203-754** — AX1, AX5
  - `tools/mutation_suite.py` writes `deterministic: True` and a fixed seed (1337) in `run.json`, but generates a wall-clock `run_id` (time-based, included in `mutation_report.json` and `run.json`), so byte-level artifacts differ across runs even with identical inputs.
- **ISSUE-20260203-755** — AX1, AX5
  - `tools/backend_contract_probe.py` writes `deterministic: True` while using a wall-clock `run_id` (time-based), so byte-level artifacts differ run-to-run even with the same `--seed` and stub backends.
- **ISSUE-20260203-756** — AX1, AX5
  - `tools/backend_fault_injector.py` writes `deterministic: True` but uses a wall-clock `run_id`, so byte-level artifacts differ across runs even with the same `--seed`.
- **ISSUE-20260203-757** — AX1, AX5
  - `tools/latency_cost_budget_enforcer.py` writes `deterministic: True` in `run.json`, but generates a wall-clock `run_id` (time-based, included in `latency_budget_report.json` and `run.json`), so byte-level artifacts differ across runs even with identical inputs + the same `--seed`.
- **ISSUE-20260203-758** — AX5, AX1
  - `tools/seed_sweep.py` records a constant `seed: 1337` in `run.json` and `seed_sweep_report.json` even when sweeping a different `--seed-start/--seed-end` range; this weakens traceability for "which seeds were tested". It also uses a wall-clock `run_id` while marking `deterministic: True`.
- **ISSUE-20260203-759** — AX1, AX5
  - `tools/harness_lattice.py` writes `deterministic: True` but generates a wall-clock `run_id` (time-based prefix) and includes it in `lattice_report.json` + `run.json`, so byte-level artifacts differ across runs even with identical inputs.
- **ISSUE-20260203-760** — AX1, AX5
  - `tools/repro_session_smoke.py` writes `deterministic: True` but uses a wall-clock `run_id`, so the emitted `run.json` + `session_report.json` metadata differ run-to-run even when `--seed` is held constant.
- **ISSUE-20260203-761** — AX3, AX5
  - `tools/ci_gate.py` spawns sub-tool run bundles but does not declare/embed them in the parent run bundle (no `child_runs/`, no `run.json.outputs` entries); sub-run locations only appear in `ci_gate_report.json.steps[].stdout_tail`.
- **ISSUE-20260203-762** — AX4, AX5
  - `tools/repro_grounding_protocol_smoke.py` emits `ci_gate_report.json` (`schema_version: ci_gate_report@1`), making schema/filename misleading.
- **ISSUE-20260203-763** — AX1, AX5, AX6
  - `tools/node_evolution_diff.py` claims `deterministic: True` but uses a wall-clock `run_id` and records raw input `before/after` paths (can leak absolute paths).
- **ISSUE-20260204-764** — AX11
  - `select_next_node` avoid-repeat rule can be undone by seed-based top-2 swap when graph has exactly 2 nodes (Heisenbug: disappears when graph grows).

- **ISSUE-20260204-769** — AX11
  - router double-clamps the assembled prompt, which can truncate away `<<<END_USER>>>` and cause stub user-extraction fallback (Heisenbug-length sensitivity).

- **ISSUE-20260204-770** — AX11
  - stub backend user-extraction can be truncated if the user message contains the sentinel marker `<<<END_USER>>>` (marker collision), flipping behavior with tiny input changes.

- **ISSUE-20260204-771** — AX1, AX3
  - parallel runs can collide on the same `run_id` (timestamp-ms + seeded random), causing run bundle overwrites/mixed artifacts.

- **ISSUE-20260204-772** — AX11
  - `build_grounding` breaks on an over-budget top snippet, dropping all grounding even when later snippets would fit (Heisenbug: toggles with tiny budget/chunk changes).

- **ISSUE-20260204-773** — AX11
  - `parse_eval_block()` post-parse substring override can force `NEXT_ACTION=CLOSE_NODE` whenever `close_node` appears anywhere in raw tutor text (even negated), causing premature node closure.

### v26 Additions
AX2↔AX11 boundary coupling; AX10 streaming gaps; AX6 FS semantics.

### v34 Additions
Boundary-only failures around torn/corrupt JSON + unbounded network response handling.

- **ISSUE-20260205-066** — AX2, AX11
  - `graph_invariant_checker` can crash on malformed JSON / bad `turn_index` after allocating run dir (empty bundle).
- **ISSUE-20260205-067** — AX2, AX10, AX11
  - `coverage_gate` can crash on truncated `coverage_raw.json` (disk-full) after allocating run dir.
- **ISSUE-20260205-068** — AX10, AX11
  - `util_http.post_json` reads entire HTTP response body into RAM (no max-bytes cap).
- **ISSUE-20260205-069** — AX11
  - `util_http.post_json` can throw unwrapped `UnicodeDecodeError` on non‑UTF8 responses.
- **ISSUE-20260205-070** — AX2, AX11
  - `ontario_claims_citation_guard` can crash on malformed JSON / bad `turn_index` after allocating run dir (empty bundle).
