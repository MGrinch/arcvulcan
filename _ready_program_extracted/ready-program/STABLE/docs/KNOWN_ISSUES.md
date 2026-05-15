# KNOWN_ISSUES.md (STABLE)
Open Issues = 130
Where to look for more detail:
- Issue entries below are the canonical open-issue record for this cleaned snapshot.
- Resolved history lives in `STABLE/docs/KNOWN_ISSUES_RESOLVED.md`.

- **ISSUE-20260206-001** — `coverage_gate` accepts NaN/Infinity thresholds (can bypass or force FAIL unpredictably). [AFM: AX5, AX11]
  - Files: `tools/coverage_gate.py`
  - Symptom: coverage gating can be bypassed or made unstable by passing non-finite float thresholds.
  - Micro-cause: argparse uses `type=float`, which accepts `nan`, `inf`, `-inf`. Comparisons with `nan` are always False, and `-inf` makes thresholds trivially pass.
  - Boundary trigger: `--min-line nan` (or `--min-branch nan`) → always FAIL; `--min-line -inf` and `--min-branch -inf` → always PASS regardless of real coverage.
  - Repro:
    - `python tools/coverage_gate.py <run_dir> --issue ISSUE-20260206-001 --min-line -inf --min-branch -inf`
    - `python tools/coverage_gate.py <run_dir> --issue ISSUE-20260206-001 --min-line nan`
  - Expected: validate thresholds are finite and within [0,100].
  - Observed: non-finite inputs are accepted; gate behavior becomes meaningless at extremes.

- **ISSUE-20260206-002** — `mirror_calibration_bench` accepts NaN/Infinity `--min-avg` and can be trivially bypassed. [AFM: AX5, AX11]
  - Files: `tools/mirror_calibration_bench.py`
  - Symptom: mirror calibration can be forced to PASS or behave inconsistently with non-finite threshold input.
  - Micro-cause: `--min-avg` is parsed as `float`; Python accepts `nan/inf/-inf`. Overall decision uses `avg_s < float(args.min_avg)`.
  - Boundary trigger: `--min-avg nan` → comparison is False → PASS even when avg is poor; `--min-avg inf` → always FAIL.
  - Repro:
    - `python tools/mirror_calibration_bench.py <session_report.json> --issue ISSUE-20260206-002 --min-avg nan`
  - Expected: enforce finite `--min-avg` in [0.0, 1.0] (or document allowed range).
  - Observed: accepts non-finite values; threshold semantics break at boundary.

- **ISSUE-20260206-003** — `doctor` can hang/OOM on huge `.md`/`.txt` because it reads entire files to count lines. [AFM: AX7, AX10, AX11]
  - Files: `tools/doctor.py`
  - Symptom: repository hygiene check (`doctor`) can stall or run out of memory when encountering very large text files.
  - Micro-cause: `_line_count(p)` uses `p.read_text(...).splitlines()` with no max-bytes guard, for suffixes that include `.md` and `.txt`.
  - Boundary trigger: a multi-GB `.md`/`.txt` (or a special file misnamed with `.txt`) anywhere under the repo tree.
  - Repro:
    - Create a large file then run `python tools/doctor.py` and observe memory/time blow-up.
  - Expected: cap bytes read / stream line count / skip huge files with a warning.
  - Observed: unbounded read can blow RAM or take extremely long, turning `doctor` into a stress hazard.

- **ISSUE-20260206-004** — `prompt_snapshot_guard` can crash on corrupt `prompt_snapshots.json` after allocating `run_dir`, leaving an empty bundle. [AFM: AX2, AX11]
  - Files: `tools/prompt_snapshot_guard.py`
  - Symptom: empty `runs/<run_id>/` directory appears when the snapshots baseline file is partially written or corrupted.
  - Micro-cause: tool allocates `run_dir` then does `baseline = json.loads(snap_path.read_text(...))` with no try/except. `JSONDecodeError` aborts before report writes.
  - Boundary trigger: torn JSON (disk-full, crash mid-write) or manual edit error in `STABLE/prompt_snapshots.json`.
  - Repro:
    - Corrupt/shorten the snapshots JSON then run `python tools/prompt_snapshot_guard.py --issue ISSUE-20260206-004`.
  - Expected: always emit an INCOMPLETE report bundle that records the parse error (AX2).
  - Observed: crash after directory creation leaves an empty run bundle (audit gap).

- **ISSUE-20260206-005** — `mutation_suite` mutates source files in-place; hard-kill/interrupt can leave the repo in a mutated state. [AFM: AX7, AX11]
  - Files: `tools/mutation_suite.py`
  - Symptom: after a kill/interrupt during builtin mutation runs, the repo can be left with mutated source code.
  - Micro-cause: tool writes mutation directly to the tracked file and relies on a `finally:` restore. SIGKILL/power loss bypasses `finally`, leaving the mutation in place.
  - Boundary trigger: CI timeout, OOM killer, abrupt process termination, IDE stop button, or machine crash mid-mutation.
  - Repro:
    - Run `python tools/mutation_suite.py --issue ISSUE-20260206-005 --engine builtin` and hard-kill between write and restore.
  - Expected: apply mutations in a temp copy (or git worktree) and never mutate the working tree directly.
  - Observed: repo hygiene can be corrupted at the worst moment (during CI), causing cascading false failures.

- **ISSUE-20260205-031** — allow_nan leaks non‑standard JSON via "canonical" writers. [AFM: AX4, AX11]
  - Files: `tools/json_canon.py` (`dumps_canonical()`), `witness/core.py` (`_stable_json()`, `write_event_json()`).
  - Symptom: payloads containing `float('nan')`, `float('inf')`, `-float('inf')` serialize as `NaN` / `Infinity` (Python default), which is **not** RFC 8259 / strict JSON.
  - Boundary trigger: non‑finite floats appear at stress edges (divide-by-zero guards, overflow sentinels, missing metrics, etc.).
  - Impact: cross‑language parsers (Go/JS strict) can fail to parse artifacts; "canonical" is not actually portable/strict.

- **ISSUE-20260205-032** — `artifact_roundtrip` cannot detect NaN/Infinity despite claiming it does. [AFM: AX4, AX11]
  - File: `tools/artifact_roundtrip.py` (docstring + `_load_json()` + use of `dumps_canonical()`).
  - Symptom: tool advertises catching "non‑JSON‑safe values (NaN/Infinity)", but it loads via stdlib `json.loads()` (accepts NaN/Infinity) and re‑dumps with defaults (allowing NaN/Infinity).
  - Boundary trigger: any artifact containing non‑finite floats will still PASS (false negative).
  - Impact: CI confidence is inflated; corrupted portability failures only appear downstream (when strict consumers read the artifact).

- **ISSUE-20260205-033** — run bundle collision possible at extreme throughput (same ms + same seed ⇒ same run_id). [AFM: AX2, AX3, AX11]
  - Pattern: `_run_id() = f"{int(time.time()*1000)}-{random.randint(1000,9999)}"` used across many tools (e.g. `tools/harness_turn.py`).
  - Micro-cause: suffix is deterministic under `random.seed(--seed)`; if two processes start within the same millisecond (CI parallelism / fast loops), they can generate identical run_ids.
  - Boundary trigger: parallel runs, tight loops, or low timer resolution VMs.
  - Impact: `allocate_run_dir(..., exist_ok=True)` reuses the same directory → mixed artifacts, overwritten files, and `run.json.outputs` can drift from reality (silent audit corruption).

- **ISSUE-20260205-034** — `run_paths._is_writable_dir()` probe file races under concurrency. [AFM: AX2, AX11]
  - File: `tools/run_paths.py` (`probe = p / ".__write_probe__"`).
  - Symptom: multiple concurrent processes use the same probe filename; one can delete or overwrite the other's probe mid-check.
  - Boundary trigger: parallel CI jobs or multi-tool orchestration on shared workspace.
  - Impact: false "not writable" results → unexpected fallback to temp `daedalus_runs`, scattering run bundles and breaking audit locality assumptions.

- **ISSUE-20260205-035** — negative latency is possible (wall-clock elapsed), allowing budget checks to PASS incorrectly. [AFM: AX11]
  - File: `xyzgl/backends/stub.py` (uses `time.time()` for elapsed latency).
  - Micro-cause: `latency_ms = int((time.time() - t0) * 1000)` can go negative if the system clock steps backward (NTP correction / VM clock skew).
  - Boundary trigger: clock adjustments during the call or unstable VM clocks.
  - Impact: `tools/latency_cost_budget_enforcer.py` aggregates `latency_ms`; negative values can reduce p95/max, masking real latency regressions (false PASS).

- **ISSUE-20260205-036** — `reground_cadence_verifier` can crash on decode/parse errors leaving an empty run dir. [AFM: AX2, AX11]
  - File: `tools/reground_cadence_verifier.py` (`_load_json()` has no try/except; `doc = _load_json(report_path)` happens after allocating `out_dir`).
  - Boundary trigger: partially-written JSON, non‑UTF8 bytes, or a truncated multi-byte character.
  - Impact: process aborts after creating `runs/<run_id>/` → empty bundle (audit gap) exactly when the verifier is needed most.

- **ISSUE-20260205-037** — issue-id validation checks format only; impossible dates and overflowed counters are accepted. [AFM: AX5, AX11]
  - File: `tools/issue_id.py` (`validate_issue_id()` only enforces `^ISSUE-\d{8}-\d{3}$`).
  - Boundary trigger: `ISSUE-20260231-001` (impossible date), or workflows that exceed 999 issues/day (NNN rollover).
  - Impact: sorting/traceability breaks silently; downstream tooling can treat invalid dates as real and mis-order audit history.

- **ISSUE-20260205-039** — `json_canon.write_json()` is non-atomic (torn JSON on crash / disk-full). [AFM: AX2, AX11]
  - File: `tools/json_canon.py` (`write_json()` uses `Path.write_text(...)` directly).
  - Boundary trigger: process kill mid-write, 99.9% disk full, network-mounted FS hiccups.
  - Impact: downstream tools that `json.loads()` without guards can crash, and existence-based checks can misclassify a torn artifact as “present”.
  - Expected: atomic write via temp file + `os.replace()` (and ideally fsync).

- **ISSUE-20260205-040** — `ci_gate` may report INCOMPLETE because it truncates stdout and loses the run path. [AFM: AX2, AX11]
  - File: `tools/ci_gate.py` (`_tail(..., n=900)` + `_extract_run_dir()` regex search on the tail).
  - Boundary trigger: very verbose steps (e.g. fuzzers / validators) push the run path earlier than the last 900 chars.
  - Impact: `session_dir` becomes `None` even though the harness succeeded → downstream validators are skipped and CI result becomes misleading.
  - Expected: emit a machine-readable sentinel line (e.g. `RUN_DIR=...`) at end, or pass run_dir via IPC rather than regex on truncated output.

- **ISSUE-20260205-041** — Protocol file load is unbounded (can hang or OOM on special/huge files). [AFM: AX3, AX10, AX11]
  - Files: `xyzgl/protocols.py` (`load_protocol_text()` calls `p.read_text(...)` after `(repo_root / rel_path).resolve()`).
  - Boundary triggers:
    - `cfg.protocol_path` points to a huge file (multi-GB) → RAM/time blow
    - `cfg.protocol_path` points to a FIFO / device file → blocking read (∞ latency)
  - Impact: `build_tutor_prompt()` stalls before any run bundle is written; harnesses can hang indefinitely.
  - Expected: enforce “must be under repo root”, max bytes, and non-regular-file rejection.

- **ISSUE-20260205-042** — `_chunk_text()` does not enforce `max_chars` when a single paragraph exceeds the limit. [AFM: AX10, AX11]
  - File: `xyzgl/grounding/corpus.py` (`_chunk_text()`).
  - Evidence: if `len(p) > max_chars` and `cur` is empty, the split condition is skipped and the oversized paragraph is appended as-is.
  - Boundary trigger: source files with extremely long paragraphs (no blank lines), or minified text.
  - Impact: grounding passages can exceed intended limits → prompt bloat and memory spikes even when `grounding_max_chars` is small.
  - Expected: hard-split long paragraphs (e.g. sliding window) so no chunk exceeds `max_chars`.

- **ISSUE-20260205-043** — `graph_invariant_checker` can crash on `last_verified_turn` despite earlier “not int” handling. [AFM: AX2, AX11]
  - File: `tools/graph_invariant_checker.py`
  - Evidence: later cross-check path uses `lvt = int(n.get("last_verified_turn", -1))` without try/except (after the first-pass validator).
  - Boundary trigger: `last_verified_turn="x"` (schema drift / corruption).
  - Impact: tool aborts instead of writing a FAIL bundle → empty run dir / audit gap under stress.

- **ISSUE-20260205-044** — `graph_invariant_checker` can leave empty run dirs on non-UTF8 or malformed JSON inputs. [AFM: AX2, AX11]
  - File: `tools/graph_invariant_checker.py` (`_load_json()` = `json.loads(p.read_text(encoding="utf-8"))`).
  - Boundary trigger: partially-written artifacts, truncated multi-byte characters, or non-UTF8 bytes.
  - Impact: crash occurs after `allocate_run_dir()` but before `_write_bundle()` writes artifacts.
  - Expected: guarded read/parse with `problems += [...]` and INCOMPLETE/FAIL output bundle.

- **ISSUE-20260205-045** — `run_paths` write-probe is TOCTOU/symlink-dangerous in attacker-controlled dirs. [AFM: AX6, AX11]
  - File: `tools/run_paths.py` (`probe = p / ".__write_probe__"; probe.write_text(...); probe.unlink(...)`).
  - Boundary trigger: `DAEDALUS_RUNS_DIR` points to a directory where `. __write_probe__` is a symlink to another file.
  - Impact: writability check can overwrite an arbitrary symlink target; also races under concurrency (already seen) but this adds a security edge.
  - Expected: use `os.open(..., O_NOFOLLOW|O_EXCL)`-style semantics or a randomized probe filename plus symlink checks.

- **ISSUE-20260205-046** — `repro_replay_diff` creates an output run dir before parsing inputs; parse errors leave empty bundles. [AFM: AX2, AX11]
  - File: `tools/repro_replay_diff.py` (allocates `out_dir = allocate_run_dir(run_id)` before `json.loads(...read_text...)`).
  - Boundary trigger: corrupt/truncated `turn_report.json` or `session_report.json`, or decode errors.
  - Impact: empty `runs/<run_id>/` directories accumulate; the tool fails without producing a report, harming the crash-to-code audit chain.
  - Expected: parse first (or catch exceptions) then always write an INCOMPLETE/FAIL report bundle.

- **ISSUE-20260205-038** — `WitnessCore` event_id uniqueness can fail at same-second throughput. [AFM: AX2, AX11]
  - File: `witness/core.py` (`created_at` uses seconds precision; `event_id` hashes `issue_id + created_at + payload`).
  - Boundary trigger: multiple identical payload events for the same issue created within the same second (batch loops / retries).
  - Impact: identical `event_id` can cause overwrites or de-duplication confusion when events are stored/merged by `event_id`, weakening the audit trail under stress.


## Axiomatic Failure Mapping (AFM)

See `STABLE/docs/AXIOMATIC_FAILURE_MAPPING.md` for the full map.
Hotspots (count of OPEN issues per axiom): AX1=19, AX2=35, AX3=7, AX4=6, AX5=40, AX6=20, AX7=6, AX8=1, AX9=1, AX10=21, AX11=75
Each issue line below includes a tag like `[AFM: AX5, AX2]`.
---

- ISSUE-20260205-023 [AFM: AX2, AX11]
  - Symptom: CI/verification tools can hang forever at the “infinite latency” boundary, producing no run bundle.
  - Micro-cause: multiple tools call `subprocess.run(...)` **without** a timeout (examples: `tools/ci_gate.py`, `tools/mutation_suite.py`, `tools/targeted_sweep.py`, `tools/apply_signal_fidelity_overlay.py`).
  - Boundary trigger: a child tool deadlocks, waits on network, or stalls on large inputs; parent tool never returns.
  - Repro: make a child command that sleeps indefinitely and run it through `ci_gate` (or point to a backend URL that never responds).
  - Expected: hard timeout + INCOMPLETE/FAIL with a written run bundle.
  - Observed: indefinite hang; audit artifacts never written.

- ISSUE-20260205-024 [AFM: AX2, AX10]
  - Symptom: tool orchestrators can OOM when a child tool prints massive stdout/stderr.
  - Micro-cause: `subprocess.run(..., capture_output=True)` buffers all output in memory (seen in `ci_gate`, `mutation_suite`, `targeted_sweep`, `apply_signal_fidelity_overlay`).
  - Boundary trigger: fuzzers / failing tests emitting huge logs, or a backend spewing errors.
  - Repro: run a child command that prints hundreds of MB and invoke via `tools/ci_gate.py` step runner path.
  - Expected: bounded capture (tail/truncate) while still writing a run bundle.
  - Observed: RAM spike → crash/kill; partial or missing outputs.

- ISSUE-20260205-025 [AFM: AX6, AX10, AX11]
  - Symptom: `DAEDALUS_GROUNDING_DIR` can escape the repo root and cause unintended file reads (privacy/portability footgun).
  - Micro-cause: `xyzgl/prompting.py` builds `gdir = (rr / cfg.grounding_dir).resolve()` with **no** “must stay under rr” enforcement.
  - Boundary trigger: `DAEDALUS_GROUNDING_DIR=/etc` (absolute), `../..` traversal, symlink chains, or pointing to huge trees.
  - Repro: set `DAEDALUS_GROUNDING_MODE=local` and `DAEDALUS_GROUNDING_DIR=/etc` then call `route_turn(...)` or run `tools/harness_turn.py` with grounding enabled.
  - Expected: grounding dir restricted to an allowlisted subtree + max-file-size + symlink policy.
  - Observed: resolver escapes; `load_corpus()` walks and reads from outside intended curriculum location.

- ISSUE-20260205-026 [AFM: AX2, AX10, AX11]
  - Symptom: `witness.core.scrub_pii()` can infinite-recurse on cyclic dict/list payloads, preventing event creation and losing the crash report.
  - Micro-cause: recursive walk has no visited-set / cycle detection (it assumes DAG-shaped JSON).
  - Boundary trigger: self-referential objects from frameworks (`obj['self']=obj`) or graph-like payloads.
  - Repro (unit): `x={}; x['self']=x; scrub_pii(x)` → `RecursionError`.
  - Expected: cycle-safe scrub (track object ids) and still write a minimal event.
  - Observed: recursion crash blocks `make_event()` and downstream artifact writing.

- ISSUE-20260205-027 [AFM: AX11]
  - Symptom: `tools/graph_invariant_checker.py` can silently accept `confidence=NaN` as “valid” under strict checks.
  - Micro-cause: it uses `cf=float(confidence)` and checks `cf < 0.0 or cf > 1.0`; for NaN, both comparisons are False.
  - Boundary trigger: upstream emits NaN (division-by-zero, missing metrics) into `knowledge_graph.json`.
  - Repro: set a node’s confidence to `NaN` and run `graph_invariant_checker --strict`.
  - Expected: NaN rejected explicitly (`math.isnan(cf)`).
  - Observed: NaN passes range gate and the report may PASS incorrectly.

- ISSUE-20260205-028 [AFM: AX2, AX11]
  - Symptom: `graph_invariant_checker` can crash on malformed `session_report.json`, leaving an empty run dir (audit gap).
  - Micro-cause: it computes `max_turn_idx = max([int(t.get('turn_index',-1)) for t in turns] or [-1])` with no per-item try/except.
  - Boundary trigger: schema drift or corruption where `turn_index` is non-int-convertible (e.g. `"x"`).
  - Repro: set `turns[0].turn_index="x"` then run `tools/graph_invariant_checker.py runs/<id> --issue ...`.
  - Expected: robust parsing with problems[] populated and a written FAIL bundle.
  - Observed: ValueError aborts tool before report write; audit incomplete.

- ISSUE-20260205-029 [AFM: AX2, AX11]
  - Symptom: protocol load can hard-fail on “exists but unreadable” paths, preventing any session output when regrounding is enabled.
  - Micro-cause: `xyzgl/protocols.py:load_protocol_text()` calls `p.read_text(...)` with no exception guard for permission errors/devices.
  - Boundary trigger: `DAEDALUS_PROTOCOL_PATH` points at a file with denied permissions or a special file that errors on read.
  - Repro: point protocol_path at a chmod 000 file and call `route_turn` with regrounding on.
  - Expected: safe fallback protocol + warning recorded in artifacts.
  - Observed: exception bubbles; session tools can fail before writing full run artifacts.

- ISSUE-20260205-030 [AFM: AX10, AX11]
  - Symptom: corpus loading can become superlinear and memory-heavy when grounding dir contains many large sources, even when `grounding_max_chars` is small.
  - Micro-cause: `xyzgl/grounding/corpus.py:load_corpus()` reads each source file fully and chunks it before retrieval; budget is applied only after retrieval.
  - Boundary trigger: thousands of files or very large curriculum sources; low-memory environments.
  - Repro: add a manifest with many large files and enable local grounding; observe RAM/time spike before prompt clamp.
  - Expected: size caps per file + streaming/early cutoff during corpus load.
  - Observed: large up-front load cost; can OOM/hang before any clamping occurs.

- ISSUE-20260205-014 [AFM: AX10, AX11]
  - Symptom: `xyzgl.util_http.post_json()` reads the entire HTTP response body into memory (`resp.read()`), so a backend that returns an extremely large body can trigger MemoryError / process kill or severe slowdown.
  - Micro-cause: `xyzgl/util_http.py` reads `resp.read()` unbounded, then `decode('utf-8')` and `json.loads(...)` (no streaming / max-bytes guard).
  - Boundary trigger: Backend returns multi-GB payload (or infinite-ish stream via chunked transfer), or memory is already pressured (~99.9% full).
  - Repro (unit):
    - Start a local HTTP server that returns a huge JSON body (e.g. tens/hundreds of MB) and call `post_json('http://127.0.0.1:PORT', {...})`; observe RAM spike / crash.
  - Expected:
    - Caller should fail fast with a bounded `HTTPError` like `response too large` and still write audit artifacts.
  - Observed:
    - Unbounded read allocates until failure; failure may be `MemoryError`, OS kill, or long stall; exception type is not wrapped as `HTTPError`.

- ISSUE-20260205-013 [AFM: AX6, AX10, AX11]
  - Symptom: `xyzgl.protocols.load_protocol_text()` can read arbitrary files outside the repo’s `documentation/` tree (absolute paths or `..`), and it reads them fully into memory with no size cap.
  - Micro-cause: `xyzgl/protocols.py` constructs `p = (repo_root / rel_path).resolve()` without enforcing that `p` stays under `repo_root` and then calls `p.read_text(...)` unbounded.
  - Boundary trigger: `DAEDALUS_PROTOCOL_PATH` is set to an absolute path (e.g. `/etc/hosts`, `/dev/zero`) or a traversal path (e.g. `../secret.txt`), or points at a very large file/device.
  - Repro (unit):
    - Set `DAEDALUS_PROTOCOL_PATH=/etc/hosts` (or `../somefile`) and run `python -c "from xyzgl.router import route_turn; print(route_turn('x',seed=1,turn_index=0))"`. For the size edge: set `DAEDALUS_PROTOCOL_PATH=/dev/zero` and observe hang/MemoryError.
  - Expected:
    - Protocol loading should restrict to an allowlist root (e.g. `documentation/protocols/`) and enforce max-bytes to prevent OOM/hangs.
  - Observed:
    - Arbitrary-file read is allowed; huge/special files can stall or crash, and the contents may be injected into prompts and artifacts.

- ISSUE-20260205-012 [AFM: AX6, AX11]
  - Symptom: `tools/curriculum_corpus_linter.py` can read files outside the intended grounding directory via path traversal in `manifest.json`.
  - Micro-cause: It resolves `fpath = (gdir / rel_path).resolve()` and checks only `fpath.exists()`, without verifying `fpath` is within `gdir`.
  - Boundary trigger: A malicious/accidental `manifest.json` entry uses `path: "../..."` or an absolute path.
  - Repro (unit):
    - In `curriculum/manifest.json`, set a source path to `"../STABLE/SPEC_v3.0.2.md"` (or any external file) and run `python tools/curriculum_corpus_linter.py --issue ISSUE-20260205-012`; it will happily read/hash the escaped file.
  - Expected:
    - Reject any resolved path not under `gdir` (fail with clear message).
  - Observed:
    - Escaped paths are accepted and scanned/hashes recorded (privacy/portability footgun).

- ISSUE-20260205-011 [AFM: AX6, AX11]
  - Symptom: `tools/secret_scanner.py` follows symlinks, so it can scan (and include snippets from) files outside the chosen `--path` root.
  - Micro-cause: The scanner walks `root.rglob('*')`, uses `p.is_file()` and `p.read_text()` (both follow symlinks), and only uses the symlink’s in-repo name for reporting.
  - Boundary trigger: Repo contains a symlink like `leak.txt -> /etc/hosts` or to any external file.
  - Repro (unit):
    - Create `ln -s /etc/hosts curriculum/leak_hosts.txt` then run `python tools/secret_scanner.py --issue ISSUE-20260205-011 --path curriculum`; observe it reads the external target (size permitting).
  - Expected:
    - Either skip symlinks or enforce that `p.resolve()` remains under `root.resolve()` before reading.
  - Observed:
    - External targets can be read and scanned; this is a privacy boundary escape.

- ISSUE-20260205-010 [AFM: AX11]
  - Symptom: `post_json()` latency measurement can go negative or become wildly inaccurate if system time jumps backwards/forwards (NTP adjust, VM resume).
  - Micro-cause: Uses `t0 = time.time()` and `time.time() - t0` instead of `time.monotonic()` for elapsed time.
  - Boundary trigger: Clock is adjusted during request, or system sleeps/resumes mid-call.
  - Repro (unit):
    - Monkeypatch `time.time` to return decreasing values around `post_json()` (or simulate via wrapper) and observe `dt_ms` negative.
  - Expected:
    - Elapsed time should be measured with a monotonic clock.
  - Observed:
    - Negative or incorrect `latency_ms` can propagate into reports/metrics.

- ISSUE-20260205-009 [AFM: AX5, AX11]
  - Symptom: `tools/atheris_fuzz_router.py` can report PASS even when the fuzz engine exits via `SystemExit` (including non-zero), masking real crashes.
  - Micro-cause: It wraps `atheris.Fuzz()` in `try/except SystemExit: pass` and then unconditionally sets `pass=True` / `status='PASS'` and exits 0.
  - Boundary trigger: Atheris terminates the process via `SystemExit` after finding a crash or for other error conditions.
  - Repro (unit):
    - Patch/monkeypatch `atheris.Fuzz` to `raise SystemExit(1)` and run the tool; it still prints PASS and returns 0.
  - Expected:
    - Treat non-zero `SystemExit.code` as FAIL (and record crash details).
  - Observed:
    - SystemExit is swallowed and success is reported.

- ISSUE-20260205-008 [AFM: AX6, AX11]
  - Symptom: `tools/apply_signal_fidelity_overlay.py` is vulnerable to Zip Slip when `--overlay` is a `.zip` (files can be written outside the temp extraction directory).
  - Micro-cause: Calls `ZipFile.extractall(tmp_dir)` without validating member paths; crafted zip entries like `../../pwned.txt` escape `tmp_dir`.
  - Boundary trigger: User supplies an untrusted `.zip` overlay (or a corrupted overlay archive).
  - Repro (unit):
    - Create a zip with a member named `../../outside.txt` and run `python tools/apply_signal_fidelity_overlay.py --issue ISSUE-20260205-008 --overlay evil.zip`; observe files written outside `runs/<run_id>/overlay_extract_tmp`.
  - Expected:
    - Reject any zip member whose normalized path is absolute or contains `..`; extract only safe members.
  - Observed:
    - Unsafe members can write outside the intended extraction sandbox.

- ISSUE-20260205-007 [AFM: AX2, AX11]
  - Symptom: enabling local grounding can hard-crash `route_turn` (and any harness that calls it) when `curriculum/manifest.json` exists but contains invalid JSON (e.g., partial download / merge conflict). This can leave an **empty run dir** (audit gap) in tools that allocate `runs/<run_id>/` before calling `route_turn`.
  - Micro-cause: `xyzgl/grounding/corpus.py:load_corpus()` calls `json.loads(...)` without catching `JSONDecodeError`, and the exception bubbles up through `build_grounding()` → `build_tutor_prompt()` → `route_turn()`.
  - Repro (unit):
    - `python - <<'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0,'.')
from xyzgl.config import XYZGLConfig
from xyzgl.router import route_turn
d = Path(tempfile.mkdtemp())
(d/'manifest.json').write_text('{bad json', encoding='utf-8')
cfg = XYZGLConfig(grounding_mode='local', grounding_dir=str(d))
route_turn('test', seed=1, cfg=cfg)
PY`

- ISSUE-20260205-006 [AFM: AX6, AX11]
  - Symptom: `curriculum/manifest.json` can reference `sources[].path` values like `../secret.txt` or an absolute path, and `load_corpus()` will read those files **outside** the grounding directory. This is a portability + privacy footgun (and a local file disclosure vector if the manifest is untrusted).
  - Micro-cause: `xyzgl/grounding/corpus.py` uses `fpath = grounding_dir / spec.path` without rejecting absolute paths or `..` traversal.
  - Repro (unit):
    - `python - <<'PY'
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0,'.')
from xyzgl.grounding.corpus import load_corpus
gd = Path(tempfile.mkdtemp())
outside = gd.parent / 'outside_secret.txt'
outside.write_text('SECRET', encoding='utf-8')
(gd/'manifest.json').write_text(json.dumps({'sources':[{'id':'s1','path':'../outside_secret.txt'}]}), encoding='utf-8')
corp = load_corpus(gd)
print(corp.passages[0].text)
PY`

- ISSUE-20260205-005 [AFM: AX2, AX10]
  - Symptom: `witness.core.scrub_pii()` can raise `RecursionError` on adversarial / extreme-depth payloads, preventing witness events from being created/written (audit loss at scale boundaries).
  - Micro-cause: `scrub_pii()` is purely recursive with no max-depth guard.
  - Repro (unit):
    - `python - <<'PY'
import sys
sys.path.insert(0,'.')
from witness.core import scrub_pii
d={}; cur=d
for _ in range(4000):
    cur['x']={}
    cur=cur['x']
scrub_pii(d)
PY`

- ISSUE-20260205-004 [AFM: AX2, AX11]
  - Symptom: `WitnessCore.make_event()` can crash with `TypeError: Object of type ... is not JSON serializable` if the payload contains non-JSON types (e.g., `bytes`, `datetime`, custom objects). This prevents event ids from being generated and blocks report writing.
  - Micro-cause: `_event_id()` hashes `_stable_json(payload)` where `_stable_json()` uses `json.dumps()` without a default encoder; `scrub_pii()` does not coerce non-JSON values.
  - Repro (unit):
    - `python - <<'PY'
import sys
sys.path.insert(0,'.')
from witness.core import WitnessCore
WitnessCore().make_event('ISSUE-20260205-004', {'blob': b'\x00'})
PY`

- ISSUE-20260205-003 [AFM: AX2, AX11]
  - Symptom: `WitnessCore.write_event_json()` crashes with `FileNotFoundError: [Errno 2] No such file or directory: ''` when given a relative filename with no directory component (e.g., `event.json`). This breaks the “write anywhere” contract and can erase audit trails in callers that write to CWD.
  - Micro-cause: `witness/core.py` calls `os.makedirs(os.path.dirname(path), exist_ok=True)`; when `path` has no directory, `os.path.dirname(path)` is `''` and `os.makedirs('')` raises.
  - Repro (unit):
    - `python - <<'PY'
import os, sys, tempfile
sys.path.insert(0,'.')
from witness.core import WitnessCore
wc = WitnessCore()
ev = wc.make_event('ISSUE-20260205-003', {'ok': True})
os.chdir(tempfile.mkdtemp())
wc.write_event_json(ev, 'event.json')
PY`

- ISSUE-20260205-002 [AFM: AX11]
  - Symptom: `xyzgl.util_http.post_json()` can crash with `UnicodeDecodeError` if the server returns non-UTF8 bytes (or a mis-declared encoding). The exception is not wrapped in `HTTPError`, so callers may crash unexpectedly instead of getting a structured backend failure.
  - Micro-cause: `raw.decode('utf-8')` is called without `errors='replace'` and `UnicodeDecodeError` is not caught.
  - Repro (unit, monkeypatch):
    - `python - <<'PY'
import sys, urllib.request
sys.path.insert(0,'.')
from xyzgl import util_http
class R:
    def read(self): return b'\xff\xfe'
    def __enter__(self): return self
    def __exit__(self, *a): return False
orig = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=None: R()
try:
    util_http.post_json('http://fake', {'x':1}, timeout_s=1)
finally:
    urllib.request.urlopen = orig
PY`

- ISSUE-20260205-001 [AFM: AX11]
  - Symptom: `xyzgl.util_http.post_json()` raises a raw `ValueError` when called with an invalid timeout (e.g., `timeout_s < 0`) instead of raising `HTTPError`. This can crash Gemini/Ollama backends (or future callers) at “negative/invalid config” boundaries.
  - Micro-cause: the `try/except` only catches `HTTPError`, `URLError`, and `socket.timeout`; it does not catch `ValueError` raised for out-of-range timeouts.
  - Repro (unit):
    - `python - <<'PY'
import sys
sys.path.insert(0,'.')
from xyzgl.util_http import post_json
post_json('http://127.0.0.1:1', {'x':1}, timeout_s=-1)
PY`

- ISSUE-20260204-784 [AFM: AX5, AX11]
  - Symptom: grounding retrieval behaves incorrectly at boundary values: `DAEDALUS_GROUNDING_MAX_SNIPPETS < 0` returns **almost all** candidates (Python slice `[: -1]`), and `DAEDALUS_GROUNDING_MAX_CHARS < 0` disables grounding entirely (budget becomes negative so the first snippet is always “too large”). This can make grounding “randomly disappear” or balloon the prompt at the edges.
  - Micro-cause:
    - `xyzgl/grounding/retrieval.py` uses `scored[: max_snippets]` without clamping `max_snippets >= 0`.
    - `xyzgl/grounding/prompting.py` sets `budget = max_chars` and breaks on `len(block) > budget` (always true when `budget < 0`).
  - Repro (unit):
    - `python - <<'PY'
import sys
sys.path.insert(0, '.')
from xyzgl.grounding.corpus import Corpus, SourceSpec, Passage
from xyzgl.grounding.retrieval import retrieve_snippets
from xyzgl.grounding.prompting import build_grounding
from pathlib import Path

# Negative max_snippets pulls 'all but last' instead of 0/default.
src = SourceSpec(id='s1', title='t', path='', tags=[], license='')
passages = [Passage(source_id='s1', source_title='t', text=f'fit up tack defect {i}', ordinal=i) for i in range(5)]
corpus = Corpus(sources=[src], passages=passages)
a = retrieve_snippets(corpus, 'fit up tack defect', max_snippets=2)
b = retrieve_snippets(corpus, 'fit up tack defect', max_snippets=-1)
print('max_snippets=2:', len(a), [s.passage_ordinal for s in a])
print('max_snippets=-1:', len(b), [s.passage_ordinal for s in b])

# Negative max_chars disables grounding even when snippets exist.
d = Path('curriculum')
t_ok, m_ok = build_grounding(d, 'fit up tack defect', max_snippets=6, max_chars=1000)
t_neg, m_neg = build_grounding(d, 'fit up tack defect', max_snippets=6, max_chars=-1)
print('max_chars=1000 snippets:', len(m_ok['snippets']))
print('max_chars=-1 snippets:', len(m_neg['snippets']))
PY`

- ISSUE-20260204-783 [AFM: AX2, AX5]
  - Symptom: tools that accept an explicit `--run-id` (confirmed: `tools/harness_session.py`) can **crash** at the filesystem boundary when the run id exceeds the platform’s filename limit (commonly 255 bytes). This produces **no run bundle** and no `run.json` (audit gap).
  - Repro:
    - `python tools/harness_session.py --issue ISSUE-20260204-783 --seed 11 --max-turns 1 --run-id "$(python -c 'print("x"*300)')"`
    - Observe `OSError: [Errno 36] File name too long` from `tools/run_paths.py:allocate_run_dir()`.

- ISSUE-20260204-782 [AFM: AX5, AX6]
  - Symptom: `allocate_run_dir()` is vulnerable to **path injection** via `--run-id` because it joins paths as `root / run_id` without sanitizing. If `run_id` is absolute (e.g. `/tmp/...`), it **overrides** the runs root; if it contains `..`, it can escape the runs folder. This breaks portability and can write run bundles to unexpected locations.
  - Micro-cause: `tools/run_paths.py` uses `out = root / run_id` and `Path` semantics treat absolute RHS as overriding the LHS; `..` segments are honored by the filesystem.
  - Repro:
    - Absolute override: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260204-782 --max-turns 1 --run-id /tmp/daedalus_abs_run`
      - stdout prints `wrote outputs to /tmp/daedalus_abs_run` (outside `$DAEDALUS_RUNS_DIR`).
    - Relative escape: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260204-782 --max-turns 1 --run-id ../escape_rel_run`
      - creates `/tmp/escape_rel_run` (sibling of the runs dir).

- ISSUE-20260204-781 [AFM: AX2, AX5]
  - Symptom: setting `DAEDALUS_PROTOCOL_PATH` to a **directory** (or other non-file path) causes an uncaught `IsADirectoryError` during prompt assembly, crashing `route_turn()` before any artifacts are written. In `tools/harness_turn.py`, the run dir is allocated **before** calling `route_turn()`, so this leaves an **empty run directory** (audit gap).
  - Micro-cause: `xyzgl/protocols.py:load_protocol_text()` checks `exists()` but does not require `is_file()`; it calls `Path.read_text()` on directories.
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs DAEDALUS_PROTOCOL_PATH=STABLE python tools/harness_turn.py --issue ISSUE-20260204-781 --seed 11 --text "hello"`
    - Observe `IsADirectoryError: .../STABLE` and then inspect the newest run dir under `$DAEDALUS_RUNS_DIR` → directory exists but contains no `turn_report.json` / `run.json`.

- ISSUE-20260204-780 [AFM: AX5, AX11]
  - Symptom: `tools/latency_cost_budget_enforcer.py` returns **PASS** when `--cases 0` (or negative), producing a report with `cases: 0` and `samples: []`. This is a boundary **no-op PASS** (it trivially satisfies thresholds with p95=0), so CI/sweeps can silently “pass” without executing any measurements.
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/latency_cost_budget_enforcer.py --issue ISSUE-20260204-780 --cases 0`
    - Inspect `<run_dir>/latency_budget_report.json` → `cases: 0`, `samples: []`, and stdout prints `PASS`.

- ISSUE-20260204-779 [AFM: AX5, AX11]
  - Symptom: `tools/harness_session.py` returns **PASS** when `--max-turns 0` (or negative), producing a `session_report.json` with **0 turns**. This is a boundary **no-op PASS** that can hide regressions (downstream tools may assume at least one turn exists).
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260204-779 --max-turns 0`
    - Inspect `<run_dir>/session_report.json` → `turns: []`, and stdout prints `PASS`.

- ISSUE-20260204-778 [AFM: AX5, AX11]
  - Symptom: `tools/seed_sweep.py` returns **PASS** when `--seed-start > --seed-end`, producing `samples: []` and `unique_replies: 0`. This is a boundary **no-op PASS** (nothing is tested).
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/seed_sweep.py --issue ISSUE-20260204-778 --seed-start 5 --seed-end 4`
    - Inspect `<run_dir>/seed_sweep_report.json` → `seed_range.start > seed_range.end`, `samples: []`, and stdout prints `PASS`.

- ISSUE-20260204-777 [AFM: AX5, AX11]
  - Symptom: `tools/property_turn_fuzzer.py` returns **PASS** when `--cases 0` (or negative), producing `results: []` and `problems: []`. This is a boundary **no-op PASS** (no properties are tested).
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/property_turn_fuzzer.py --issue ISSUE-20260204-777 --cases 0`
    - Inspect `<run_dir>/property_fuzz_report.json` → empty `results`, and stdout prints `PASS`.

- ISSUE-20260204-776 [AFM: AX2, AX5]
  - Symptom: `tools/property_turn_fuzzer.py` **crashes** when `--max-len < 0` with `ValueError: empty range for randrange()`, **after** it allocates a run dir. This leaves an **empty run directory** with no `run.json` / report artifacts (audit gap).
  - Micro-cause: `_gen_case()` calls `randint(0, max_len)`; a negative `max_len` triggers `randrange()` failure.
  - Repro:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/property_turn_fuzzer.py --issue ISSUE-20260204-776 --cases 5 --max-len -1`
    - Observe a traceback; then check the newest `<run_dir>/` under `$DAEDALUS_RUNS_DIR` → directory exists but is empty.

- ISSUE-20260204-775 [AFM: AX6, AX11]
  - Symptom: on Windows / CRLF curriculum files, grounding chunking fails to split on blank lines, so passages become huge and can exceed budgets; grounding may abruptly disappear (often cascading into the AX11 grounding-budget break).
  - Evidence: `xyzgl/grounding/corpus.py:_chunk_text()` splits paragraphs using `text.split("\n\n")`. With CRLF blank lines (`\r\n\r\n`), there is no `\n\n` substring, so the entire document becomes one 'paragraph' and a single oversized chunk.
  - Repro (unit):
    - `python - <<'PY'
from xyzgl.grounding.corpus import _chunk_text
t_lf = 'P1\n\nP2\n\nP3\n\n'
t_crlf = 'P1\r\n\r\nP2\r\n\r\nP3\r\n\r\n'
print('LF chunks:', len(_chunk_text(t_lf, max_chars=4)))
print('CRLF chunks:', len(_chunk_text(t_crlf, max_chars=4)))
print('CRLF chunk_len:', len(_chunk_text(t_crlf, max_chars=4)[0]))
PY`
    - Expected: both LF and CRLF should produce ~3 chunks (one per paragraph).
    - Actual: CRLF produces 1 huge chunk (paragraph split never triggers).
  - Integration fracture: retrieval excerpts become much larger on CRLF corpora, pushing grounding over `max_chars` and making grounding appear 'intermittent' across editors/OS (saving the same file with LF can make it disappear).

- ISSUE-20260204-774 [AFM: AX5]
  - Symptom: run bundles appear to “disappear” or land in unexpected locations because `tools/run_paths.py` chooses `Path("runs")` relative to the *current working directory* (CWD), not repo root.
  - Why it’s Heisenbug-like: when you “look” (run from VS Code / repo root), artifacts land in `repo_root/runs/`; when you run from inside `tools/` or via a shortcut with a different CWD, artifacts land in `tools/runs/` (or elsewhere), so it feels intermittent.
  - Micro-cause: `runs_root()` prefers `cwd/runs` when writable; CWD changes across launch methods.
  - Repro (Windows):
    - From repo root: `py tools\harness_turn.py --issue ISSUE-20260204-774 --text "test"`
      - output dir: `runs\<run_id>\...`
    - Then: `cd tools` and run: `py harness_turn.py --issue ISSUE-20260204-774 --text "test"`
      - output dir: `tools\runs\<run_id>\...`
- ISSUE-20260202-716 [AFM: AX1]
  - Symptom: full-file determinism hashing fails even with fixed `--seed` because artifacts include time/latency fields.
  - Repro: run `tools/harness_turn.py` twice with same seed; hash whole `turn_report.json` (differs); hash a “semantic core” excluding time/latency (stable).
- ISSUE-20260202-714 [AFM: AX3]
  - Symptom: some tools create artifacts that are missing from `run.json.outputs` (often nested `child_runs/` or summary `.md`).
  - Repro: run `tools/coverage_gate.py` then compare filesystem vs `run.json.outputs` (nested bundles + summaries can be omitted).
  - Confirmed example: `tools/mirror_calibration_bench.py` writes `mirror_calibration_summary.md` but does not list it in `run.json.outputs`.
  - Confirmed example: `tools/coverage_gate.py` creates `child_runs/` sub-bundles but does not include `child_runs/...` in the parent `run.json.outputs`.
- ISSUE-20260201-701 [AFM: AX7]
  - Symptom: `tools/targeted_sweep.py` can self-sabotage `doctor` by generating artifacts before running `doctor` (fails in a clean repo).
  - Workaround: run under `DAEDALUS_RUNS_DIR=/tmp/...` so repo stays clean; or reorder sweep steps.
- ISSUE-20260201-702 [AFM: AX2]
  - Symptom: several tools FAIL/INCOMPLETE on missing/invalid inputs without emitting any audit bundle (no run dir, no `run.json`).
  - Repro: call one of these with missing paths: `node_evolution_diff`, `repro_replay_diff`, `artifact_roundtrip`, `protocol_drift_radar`, `mirror_*`, `graph_invariant_checker`, `reground_cadence_verifier`.
- ISSUE-20260201-703 [AFM: AX5]
  - Symptom: `tools/ci_gate.py` cannot locate the harness session run dir when `DAEDALUS_RUNS_DIR`’s folder name is not exactly `runs` or `daedalus_runs`.
  - Repro: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs_ci_clean python tools/ci_gate.py ...` → step `session_run_dir` INCOMPLETE.
- ISSUE-20260202-717 [AFM: AX4]
  - Symptom: multiple tools write non-canonical `run.json` (not using `json_canon.write_json`), so `tools/artifact_roundtrip.py --strict` would rewrite it (strict FAIL).
  - Confirmed (strict mismatch changes `run.json`): `secret_scanner`, `stage_timing_profiler`, `prompt_snapshot_guard`, `atheris_fuzz_router`, `ci_gate`, `graph_invariant_checker`, `mirror_calibration_bench`, `mirror_leakage_detector`, `property_turn_fuzzer`, `redteam_injection_suite`, `redteam_rag_poisoning_suite`, `reground_cadence_verifier`, `repro_replay_diff`.
  - Suspected by static inspection: (none currently; the prior list was confirmed via ART strict roundtrip).
  - Repro: run a confirmed tool under `DAEDALUS_RUNS_DIR=/tmp/...`, then `python tools/artifact_roundtrip.py --issue <same ISSUE> --strict <run_dir>` → report shows `changed: True` for `<run_dir>/run.json`.
- ISSUE-20260202-916 [AFM: AX4]
  - Symptom: `tools/coverage_gate.py` produces vendor-raw `coverage_raw.json` (coverage.py JSON) that fails canonical strict roundtrip.
  - Repro: run `coverage_gate`, then `artifact_roundtrip --strict` on the run dir → `coverage_raw.json` changed.
- ISSUE-20260202-718 [AFM: AX5]
  - Symptom: `tools/repro_replay_diff.py` accepts `--issue` but does not validate `ISSUE-YYYYMMDD-NNN`.
  - Repro: `python tools/repro_replay_diff.py --issue NOT-AN-ISSUE ...` writes invalid `issue_id` into artifacts.
- ISSUE-20260202-719 [AFM: AX8]
  - Symptom: shipped Signal Fidelity overlay is `.rar` (not stdlib-friendly), so `apply_signal_fidelity_overlay` can be INCOMPLETE without an external extractor.
- ISSUE-20260202-705 [AFM: AX10]
  - Symptom: `tools/harness_session.py` report size grows linearly with `--max-turns` (large JSON for long runs).
  - Workaround: keep `--max-turns` modest; consider streaming/compression.
- ISSUE-20260202-725 [AFM: AX5]
  - Symptom: many tools accept `--issue` but do not validate it (malformed IDs can enter run bundles).
  - Notes: `tools/targeted_sweep.py` validates via regex but returns FAIL (1) instead of the repo convention INCOMPLETE (2).
  - Affected tools (repo scan):
    - apply_signal_fidelity_overlay, atheris_fuzz_router, backend_fault_injector
    - curriculum_corpus_linter, graph_invariant_checker, grounding_injection_audit
    - latency_cost_budget_enforcer, ontario_claims_citation_guard, property_turn_fuzzer
    - redteam_injection_suite, redteam_rag_poisoning_suite
    - repro_backends_smoke, repro_grounding_protocol_smoke, repro_replay_diff
    - retrieval_eval_bench, seed_sweep
- ISSUE-20260202-726 [AFM: AX6]
  - Symptom: `session_report.json` records absolute `grounding_dir` paths (non-portable + can leak local filesystem layout).
- ISSUE-20260202-727 [AFM: AX5]
  - Symptom: stdout “run dir” contract varies (`wrote outputs to <dir>` vs `(...wrote <dir>)`), breaking stdout-parsing meta-tools.
- ISSUE-20260202-728 [AFM: AX9]
  - Symptom: `artifact_schemas/` is documented as an alias copy of `schemas/`, but it is only a partial subset (5 files vs 36).
  - Repro: `ls schemas/*.json | wc -l` vs `ls artifact_schemas/*.json | wc -l`.
- ISSUE-20260202-729 [AFM: AX2]
  - Symptom: `tools/ontario_claims_citation_guard.py` can leave an **empty** run dir on early FAIL (allocates run dir, then exits without writing artifacts).
  - Repro: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/ontario_claims_citation_guard.py --enforce /tmp/does_not_exist`.
- ISSUE-20260202-730 [AFM: AX7]
  - Symptom: `tools/artifact_roundtrip.py` bytecode guard is too late; running `python tools/artifact_roundtrip.py --help` can create `tools/__pycache__/` and fail `doctor`.
- ISSUE-20260202-731 [AFM: AX3, AX4]
  - Symptom: `tools/artifact_roundtrip.py` only checks top-level `*.json` files when given a run directory and ignores nested run bundles under `child_runs/`.
  - Risk: a parent bundle can PASS/FAIL without detecting non-canonical JSON (or other violations) inside nested bundles.
  - Repro: run `tools/coverage_gate.py` (creates `child_runs/`), then run `tools/artifact_roundtrip.py --strict <coverage_run_dir>` and observe only top-level JSON is reported.
- ISSUE-20260202-732 [AFM: AX5]
  - Symptom: `tools/artifact_roundtrip.py` returns exit code 2 (INCOMPLETE) for invalid `--issue`, but its module docstring and run bundle metadata advertise only exit codes 0/1.
  - Repro: `python tools/artifact_roundtrip.py --issue NOT-AN-ISSUE --strict runs/<run_id>/; echo $?` (returns 2).
- ISSUE-20260202-733 [AFM: AX3]
  - Symptom: `tools/validate_schemas.py` validates only a fixed set of filenames at the top level of a run directory and does not recurse into nested run bundles (e.g., `child_runs/`).
  - Risk: schema violations inside nested bundles can go undetected when validating a parent bundle.
  - Repro: run `tools/coverage_gate.py` (creates `child_runs/`), then run `tools/validate_schemas.py <coverage_run_dir>` and observe it does not inspect JSON under `child_runs/`.

---
- ISSUE-20260203-734 [AFM: AX6]
  - Symptom: `tools/artifact_roundtrip.py` report embeds absolute filesystem paths in `files[].file` and `path`, leaking local layout and breaking portability.
  - Repro: run `artifact_roundtrip --strict` on any run dir; inspect `artifact_roundtrip_report.json` → `file` like `/tmp/daedalus_runs/.../run.json`.
- ISSUE-20260203-735 [AFM: AX11]
  - Symptom: `tools/secret_scanner.py` intends to allow obvious placeholders (`YOUR_API_KEY`, `<redacted>`), but the allowlist branch is a no-op (`pass`), so placeholders can still be flagged (false positives).
  - Repro: place a test string containing `YOUR_API_KEY` near a token-like pattern; run `secret_scanner --enforce` and observe hits are still reported.
- ISSUE-20260203-736 [AFM: AX1]
  - Symptom: `tools/secret_scanner.py` iterates files via `Path.rglob("*")` without sorting, so hit ordering can vary across filesystems/OS, weakening reproducibility of `secret_scan_report.json`.
  - Repro: run `secret_scanner` on two machines (or filesystems) with same repo; compare `hits[]` ordering.
- ISSUE-20260203-737 [AFM: AX5]
  - Symptom: multiple tools document exit codes as only `0/1`, but return `2` (INCOMPLETE) for invalid issue IDs (confirmed: `secret_scanner`, `stage_timing_profiler`, `prompt_snapshot_guard`).
  - Risk: automation/scripts relying on documented exit codes mis-handle INCOMPLETE vs FAIL.
  - Repro: `python tools/prompt_snapshot_guard.py --issue NOT-AN-ISSUE; echo $?` (prints INCOMPLETE and returns 2).
- ISSUE-20260203-738 [AFM: AX1, AX5]
  - Symptom: `tools/ontario_claims_citation_guard.py` writes `deterministic: True` in `run.json` even though it generates a wall-clock run_id and embeds it in the report (byte-level outputs vary run-to-run).
  - Repro: run `ontario_claims_citation_guard` twice on the same input with same seed; compare `ontario_claims_report.json` and see `run_id` differs while `deterministic` remains `True`.
- ISSUE-20260203-739 [AFM: AX1, AX11]
  - Symptom: `tools/secret_scanner.py` stops after 50 hit-files, but file traversal is unsorted, so the *set* of reported hits can vary across OS/filesystems (not just ordering).
  - Repro: create >50 token-like files; run on different filesystems; compare `hits[].file` subset.
- ISSUE-20260203-740 [AFM: AX6]
  - Symptom: `tools/prompt_snapshot_guard.py` writes an absolute `baseline_path` into `prompt_snapshot_report.json`, leaking local filesystem layout.
  - Repro: run `prompt_snapshot_guard`; inspect `baseline_path` contains a full local path.
- ISSUE-20260203-741 [AFM: AX11]
  - Symptom: `tools/ci_gate.py` runs `secret_scanner` without `--enforce`, so secrets can be detected in the report but CI still passes that step (exit code 0).
  - Repro: add a temp file containing `sk-...`; run `ci_gate --issue ...`; observe `secret_scanner` step exit_code is 0 unless `--enforce` is used.
- ISSUE-20260203-742 [AFM: AX6, AX1]
  - Symptom: `tools/grounding_injection_audit.py` writes `grounding_dir_abs` (resolved absolute path) into `grounding_audit_report.json`.
  - Repro: run `python tools/grounding_injection_audit.py --issue ISSUE-20260203-742` then inspect the report for an absolute `grounding_dir_abs` value.
- ISSUE-20260203-743 [AFM: AX6, AX1]
  - Symptom: `tools/curriculum_corpus_linter.py` stores a resolved absolute `grounding_dir` in `corpus_lint_report.json`.
  - Repro: run `python tools/curriculum_corpus_linter.py --issue ISSUE-20260203-743` then inspect the report `grounding_dir` value.
- ISSUE-20260203-744 [AFM: AX7, AX6]
  - Symptom: `tools/apply_signal_fidelity_overlay.py` writes overlay contents into repo-root `signal_fidelity_src/` (outside the run bundle) and records `out_root_abs` in the report.
  - Repro: run `python tools/apply_signal_fidelity_overlay.py --issue ISSUE-20260203-744` (with any overlay source) and observe repo-root `signal_fidelity_src/` plus `out_root_abs` in `signal_fidelity_apply_report.json`.
- ISSUE-20260203-745 [AFM: AX1, AX5]
  - Symptom: `tools/doc_code_link_checker.py` writes `deterministic: True` in `run.json` even though it generates a wall-clock `run_id` and embeds it in artifacts (byte-level outputs vary run-to-run).
  - Repro: run `python tools/doc_code_link_checker.py --issue ISSUE-20260203-745` twice; compare the generated `run.json` / report → `run_id` differs.
- ISSUE-20260203-746 [AFM: AX6]
  - Symptom: `tools/graph_invariant_checker.py` records the raw input `path` as `source` in `graph_invariant_report.json`; if invoked with an absolute path, it leaks local filesystem layout and breaks portability.
  - Repro: `python tools/graph_invariant_checker.py /tmp/daedalus_runs/<run_id> --issue ISSUE-20260203-746` then inspect `graph_invariant_report.json.source`.
- ISSUE-20260203-747 [AFM: AX6, AX1]
  - Symptom: multiple tools embed raw input paths (often absolute) in report fields like `source` or `target` while also claiming `deterministic: True` in `run.json` despite time-based `run_id` generation.
  - Affected tools (confirmed): `protocol_drift_radar`, `mirror_calibration_bench`, `mirror_leakage_detector`, `reground_cadence_verifier`, `repro_replay_diff`.
  - Repro: invoke a listed tool with an absolute `path`; inspect the report (`*_report.json.source` or `*_report.json.target`) and the run bundle `run.json.deterministic` vs time-based `run_id`.
- ISSUE-20260203-748 [AFM: AX1, AX5]
  - Symptom: `tools/ci_gate.py --seed X` does not propagate the seed to all sub-tools; some sub-runs silently use their default seed (often 1337).
  - Impact: CI bundles are not seed-consistent, weakening determinism and replay comparisons.
  - Evidence (confirmed): in a single `ci_gate --seed 11` run, `backend_contract_probe` + `harness_session` used seed 11, but `secret_scanner`, `prompt_snapshot_guard`, and `stage_timing_profiler` ran with seed 1337 (read from their `run.json`).
  - Repro: run `DAEDALUS_RUNS_DIR=/tmp/... python tools/ci_gate.py --issue ISSUE-20260203-748 --seed 11`; parse sub-run dirs from `ci_gate_report.json.steps[].stdout_tail`; open each sub-run `run.json` and compare `seed`.
- ISSUE-20260203-749 [AFM: AX6]
  - Symptom: grounding stores verbatim excerpt text inside run artifacts (e.g., `prompt_meta.grounding.snippets[].excerpt`), so sharing run bundles can leak corpus content (copyright/proprietary text, internal SOPs, etc.).
  - Evidence: `xyzgl/grounding/prompting.py` adds `asdict(sn)` (includes `excerpt`) into grounding meta; session/turn reports persist `prompt_meta`.
  - Repro: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260203-749 --seed 11 --max-turns 1 --grounding`; inspect `session_report.json` for `excerpt`.
- ISSUE-20260203-750 [AFM: AX10]
  - Symptom: enabling grounding inflates `session_report.json` substantially because excerpts are duplicated (in `grounding_text` and in `prompt_meta.grounding.snippets[].excerpt`); report size scales with turns × snippet budget.
  - Repro: run twice and compare sizes:
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260203-750 --seed 11 --max-turns 3`
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260203-750 --seed 11 --max-turns 3 --grounding`
- ISSUE-20260203-751 [AFM: AX2, AX6]
  - Symptom: `tools/retrieval_eval_bench.py` allocates a run dir, then returns INCOMPLETE early (missing/empty bench or empty corpus) without writing `run.json` / report artifacts, leaving an empty run directory (audit gap).
  - Symptom: default `--bench` / `--grounding-dir` are interpreted relative to the current working directory (CWD), so invoking the tool from outside the repo commonly triggers the early-INCOMPLETE path.
  - Repro (empty run dir):
    - `cd /tmp`
    - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python /path/to/repo/tools/retrieval_eval_bench.py --issue ISSUE-20260203-751`
    - Observe: a new run dir is created under `DAEDALUS_RUNS_DIR`, but it contains **no files**.
- ISSUE-20260203-752 [AFM: AX5, AX7]
  - Symptom: `tools/run_paths.py` chooses `Path('runs')` relative to the current working directory (CWD). If you run tools from a subfolder (e.g., `cd tools`), run bundles land in `tools/runs/<run_id>` instead of the repo-root `runs/` (or `$DAEDALUS_RUNS_DIR`), contaminating the repo and breaking run-path assumptions.
  - Repro: `cd tools && python harness_turn.py --issue ISSUE-20260203-752` → run dir created under `tools/runs/`. Then `cd .. && python tools/doctor.py --lenient` does not warn about `tools/runs/` because it only checks repo-root `runs/`.
- ISSUE-20260203-753 [AFM: AX1, AX5]
  - Symptom: `tools/curriculum_corpus_linter.py` writes `deterministic: True` in `run.json`, but its `run_id` is wall-clock based (and written into `corpus_lint_report.json`), so byte-level outputs vary run-to-run even with the same `--seed`.
  - Impact: tooling that treats `deterministic: True` as “byte-stable under seed” will misclassify these run bundles; diffing/hashing full artifacts is unstable.
  - Repro: run twice with the same seed: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/curriculum_corpus_linter.py --issue ISSUE-20260203-753 --seed 11` then compare `corpus_lint_report.json.run_id` and `run.json.run_id` (differs).

- ISSUE-20260203-754 [AFM: AX1, AX5]
  - Symptom: `tools/mutation_suite.py` writes `deterministic: True` and a fixed seed (1337) in `run.json`, but generates a wall-clock `run_id` (time-based, included in `mutation_report.json` and `run.json`), so byte-level artifacts differ across runs even with identical inputs.
  - Symptom: the tool does not accept `--seed`, so CI/sweeps cannot align mutation runs to a single requested seed, and the determinism metadata is easy to misinterpret.
  - Repro: run twice: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/mutation_suite.py --issue ISSUE-20260203-754 --engine builtin --target xyzgl` then compare the two run bundles’ `run.json.run_id` values (differs).
- ISSUE-20260203-755 [AFM: AX1, AX5]
  - Symptom: `tools/backend_contract_probe.py` writes `deterministic: True` while using a wall-clock `run_id` (time-based), so byte-level artifacts differ run-to-run even with the same `--seed` and stub backends.
  - Evidence: same `--seed 11` produces identical random suffix but different timestamp prefix in `run_id`.
  - Repro: run twice: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/backend_contract_probe.py --issue ISSUE-20260203-755 --seed 11` and compare `run.json.run_id` / `backend_contract_report.json.run_id` (differs).
- ISSUE-20260203-756 [AFM: AX1, AX5]
  - Symptom: `tools/backend_fault_injector.py` writes `deterministic: True` but uses a wall-clock `run_id`, so byte-level artifacts differ across runs even with the same `--seed`.
  - Repro: run twice: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/backend_fault_injector.py --issue ISSUE-20260203-756 --seed 11` and compare the two run bundles’ `run.json.run_id` (differs).
- ISSUE-20260203-757 [AFM: AX1, AX5]
  - Symptom: `tools/latency_cost_budget_enforcer.py` writes `deterministic: True` in `run.json`, but generates a wall-clock `run_id` (time-based, included in `latency_budget_report.json` and `run.json`), so byte-level artifacts differ across runs even with identical inputs + the same `--seed`.
  - Repro: run twice: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/latency_cost_budget_enforcer.py --issue ISSUE-20260203-757 --seed 11` then compare the two run bundles' `run.json.run_id` values (differs).
- ISSUE-20260203-758 [AFM: AX5, AX1]
  - Symptom: `tools/seed_sweep.py` records a constant `seed: 1337` in `run.json` and `seed_sweep_report.json` even when sweeping a different `--seed-start/--seed-end` range; this weakens traceability for "which seeds were tested". It also uses a wall-clock `run_id` while marking `deterministic: True`.
  - Repro: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/seed_sweep.py --issue ISSUE-20260203-758 --seed-start 11 --seed-end 12` then inspect `run.json.seed` and `seed_sweep_report.json.seed` (both 1337) vs `seed_range` + `samples[].seed`.
- ISSUE-20260203-759 [AFM: AX1, AX5]
  - Symptom: `tools/harness_lattice.py` writes `deterministic: True` but generates a wall-clock `run_id` (time-based prefix) and includes it in `lattice_report.json` + `run.json`, so byte-level artifacts differ across runs even with identical inputs.
  - Repro: run twice with identical args: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_lattice.py --issue ISSUE-20260203-759` then compare the two run bundles' `run.json.run_id` (differs).
- ISSUE-20260203-760 [AFM: AX1, AX5]
  - Symptom: `tools/repro_session_smoke.py` writes `deterministic: True` but uses a wall-clock `run_id`, so the emitted `run.json` + `session_report.json` metadata differ run-to-run even when `--seed` is held constant.
  - Repro: run twice: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/repro_session_smoke.py --issue ISSUE-20260203-760 --seed 11` and compare `run.json.run_id` (differs).
- ISSUE-20260203-761 [AFM: AX3, AX5]
  - Symptom: `tools/ci_gate.py` spawns multiple sub-tools that each write their own run bundles, but the parent `ci_gate` bundle does **not** declare or embed those sub-run dirs (no `child_runs/` and no entries in `run.json.outputs`). The only sub-run pointers are buried inside `ci_gate_report.json.steps[].stdout_tail`, forcing brittle stdout parsing.
  - Impact: CI audit bundles are incomplete/non-portable; automated tooling cannot reliably traverse the full CI evidence without regexing stdout.
  - Repro: run `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/ci_gate.py --issue ISSUE-20260203-761 --seed 1337`; observe multiple sibling run dirs created under `$DAEDALUS_RUNS_DIR`, but the parent `run.json.outputs` lists only `ci_gate_report.json`, `ci_gate_summary.md`, `run.json`.
- ISSUE-20260203-762 [AFM: AX4, AX5]
  - Symptom: `tools/repro_grounding_protocol_smoke.py` emits `ci_gate_report.json` (`schema_version: ci_gate_report@1`), so schema/filename are misleading for downstream tooling.
  - Repro: `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/repro_grounding_protocol_smoke.py --issue ISSUE-20260203-762 --seed 11` → bundle contains `ci_gate_report.json`.

- ISSUE-20260203-763 [AFM: AX1, AX5, AX6]
  - Symptom: `tools/node_evolution_diff.py` writes `deterministic: True` in `run.json` but generates a wall-clock `run_id` (time-based) so byte-level artifacts differ run-to-run even with the same `--seed` and inputs.
  - Symptom: the tool stores raw input paths in the report (`before`, `after`); if invoked with absolute paths, it leaks local filesystem layout and breaks portability.
  - Repro:
    - Generate two session runs with fixed IDs:
      - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260203-763 --seed 11 --max-turns 2 --run-id ART763_session_a`
      - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/harness_session.py --issue ISSUE-20260203-763 --seed 12 --max-turns 2 --run-id ART763_session_b`
    - Run `node_evolution_diff` twice with the same args:
      - `DAEDALUS_RUNS_DIR=/tmp/daedalus_runs python tools/node_evolution_diff.py /tmp/daedalus_runs/ART763_session_a/knowledge_graph.json /tmp/daedalus_runs/ART763_session_b/knowledge_graph.json --session-report /tmp/daedalus_runs/ART763_session_b/session_report.json --issue ISSUE-20260203-763 --seed 11` (run 1)
      - repeat the exact same command (run 2)
    - Observe: two different run bundle dirs are created (different `run.json.run_id`) while both bundles claim `deterministic: True`; `node_evolution_report.json.before/after` embed the absolute paths.

- ISSUE-20260204-764 [AFM: AX11]
  - Symptom: `select_next_node(..., avoid_node_id=<last>)` can still return the avoided node when the graph has exactly 2 nodes, depending on `seed`. This creates a Heisenbug feel: adding a third node (or changing confidences slightly) makes it “disappear.”
  - Evidence: `xyzgl/knowledge/heuristics.py` applies the avoid-rotation *before* a seed-based top-2 swap; with 2 nodes, the swap can undo the avoid step.
  - Repro (unit):
    - `python -c "from xyzgl.knowledge.graph import KnowledgeGraph, Node; from xyzgl.knowledge.heuristics import select_next_node; g=KnowledgeGraph(nodes=[Node('A','A','',[],confidence=0.0,fragility_flags=[]), Node('B','B','',[],confidence=1.0,fragility_flags=[])]);
for s in [1,2,3,4,5,6,7,8,9,10]:
    n=select_next_node(g, seed=s, avoid_node_id='A');
    print(s, n.node_id)"`
    - Expected: always `B` (since `avoid_node_id='A'` and an alternative exists).
    - Actual: some seeds return `A`.
  - Integration fracture: early sessions (2-node graphs) can “randomly” repeat the same fragile node, causing loops or premature closure heuristics to misfire; logs/debug edits that change seed/order can mask it.

- ISSUE-20260204-769 [AFM: AX11]
  - Symptom: router performs a second clamp on the *assembled* prompt to `max_chars_in`, which can truncate away `<<<END_USER>>>` and tail user tokens when grounding/protocol text expands.
  - Evidence: `xyzgl/router.py` clamps user text and then clamps the final prompt again; `xyzgl/backends/stub.py::_extract_user` falls back to treating the entire prompt as user text if the closing marker is missing.
  - Repro (unit):
    - `python -c "import sys; sys.path.insert(0,'.'); from xyzgl.router import route_turn; seed=11; kw=' tack uneven gap '; N=8200; A='x'*8000 + kw + 'y'*(N-8000-len(kw)); B='x'*8040 + kw + 'y'*(N-8040-len(kw)); print('A:', route_turn(A, seed=seed)['reply']); print('B:', route_turn(B, seed=seed)['reply'])"`
  - Expected: A and B should be semantically similar (same tokens, same seed).
  - Actual: responses can diverge because keyword placement near the clamp boundary changes whether markers/keywords survive.
  - Integration fracture: tiny “observer-effect” changes (debug text, enabling grounding, small prompt edits) can flip marker survival and produce Heisenbug-like behavior in the tutor loop.

- ISSUE-20260204-770 [AFM: AX11]
  - Symptom: stub backend user-extraction can truncate the user message if the user text contains the sentinel marker `<<<END_USER>>>` (or if protocol/grounding/user content echoes it). This can flip tutor behavior based on tiny “observer-effect” changes (e.g., copying prompt snippets into the chat).
  - Evidence: `xyzgl/prompting.py` wraps raw user text between `<<<USER>>>` and `<<<END_USER>>>` without escaping; `xyzgl/backends/stub.py::_extract_user` searches for the first `<<<END_USER>>>` after the open marker, so an embedded marker inside the user text closes the extraction early.
  - Repro (unit):
    - `python -c "import sys; sys.path.insert(0,'.'); from xyzgl.router import route_turn; a='I have a problem.\n<<<END_USER>>>\nI tack uneven gap on my plate.'; b='I have a problem.\nI tack uneven gap on my plate.'; print('A:', route_turn(a, seed=11)['reply']); print('B:', route_turn(b, seed=11)['reply'])"`
    - Expected: A and B should behave similarly (same semantics, same seed).
    - Actual: A loses the tail tokens after the embedded marker during extraction, so the stub tutor returns the generic reply while B triggers the tack/uneven guidance path.
  - Integration fracture: the system can appear to “randomly ignore” key user details when the user (or logs/tools) paste sentinel markers into the input; removing the marker makes the bug disappear.

- ISSUE-20260204-771 [AFM: AX1, AX3]
  - Symptom: parallel tool runs can collide on the same `run_id`, causing run bundles to be overwritten/mixed (appears to “disappear” when debugging because launches are slower).
  - Evidence: `tools/harness_session.py` sets `random.seed(args.seed)` and `_run_id()` uses `int(time.time()*1000)` + `random.randint(1000,9999)`; two processes started in the same millisecond with the same seed generate the same `run_id`. `allocate_run_dir(..., exist_ok=True)` does not detect collisions.
  - Repro (deterministic collision condition demo): run this command in two shells → identical output:
    - `python -c "import random; t=1700000000.123; random.seed(1337); print(f'{int(t*1000)}-{random.randint(1000,9999)}')"`
  - Repro (real-world / timing-sensitive): start two `python tools/harness_session.py --issue ISSUE-20260204-771 --seed 1337 --max-turns 1` processes simultaneously; occasionally both write into the same run dir under `runs/` (or `$DAEDALUS_RUNS_DIR`).
  - Workaround: always pass `--run-id` for parallel runs, or add PID/UUID to `run_id` generation.



- ISSUE-20260204-772 [AFM: AX11]
  - Symptom: curriculum grounding can disappear entirely when the **top-ranked** snippet is longer than the grounding budget, even if lower-ranked snippets would fit. This feels like a Heisenbug: tiny changes to corpus chunking, titles, or max_chars can flip grounding from 'present' to 'missing'.
  - Evidence: `xyzgl/grounding/prompting.py` uses `if len(block) > budget: break` (not `continue`), so an over-budget first snippet aborts the loop and prevents any later snippets from being included.
  - Repro (unit; shows empty grounding even though a small snippet exists):
    - `python - <<'PY'
import tempfile, json
from pathlib import Path
from xyzgl.grounding.prompting import build_grounding

query='weld tack gap'
with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    (d/'manifest.json').write_text(json.dumps({
        'sources':[
            {'id':'A','title':'Long','path':'a.txt','tags':[],'license':''},
            {'id':'B','title':'Short','path':'b.txt','tags':[],'license':''},
        ]
    }), ensure_ascii=False), encoding='utf-8')
    (d/'a.txt').write_text(('weld tack gap ' * 2000).strip(), encoding='utf-8')  # huge but few unique tokens → highest score
    (d/'b.txt').write_text('weld tack gap plus many extra unique tokens alpha beta gamma delta epsilon', encoding='utf-8')

    t1, m1 = build_grounding(d, query, max_snippets=6, max_chars=200)
    print('budget=200 → grounding_len', len(t1), 'snippets_used', len(m1.get('snippets',[])))

    t2, m2 = build_grounding(d, query, max_snippets=6, max_chars=40000)
    print('budget=40000 → grounding_len', len(t2), 'snippets_used', len(m2.get('snippets',[])))
PY`
    - Expected: with budget=200, at least the small snippet (B) should be included.
    - Actual: budget=200 yields `snippets_used=0` (grounding disappears), because snippet A is too big and the loop breaks before considering B.
  - Integration fracture: enabling grounding + small budget (or a single oversized chunk) can make the tutor abruptly stop citing/using sources; adding/removing a newline in corpus text (changing chunk size) can make the issue 'disappear'.

- ISSUE-20260204-773 [AFM: AX11]
  - Symptom: `parse_eval_block()` can incorrectly force `NEXT_ACTION = CLOSE_NODE` whenever the raw tutor text contains the substring `close_node` (even in negations like “do not close_node yet”, examples, or citations).
  - Evidence: `xyzgl/orchestrator/parsing.py` applies a post-parse override:
    - `if "close_node" in raw.lower() ...: out["next_action"] = "CLOSE_NODE"`
    - This can overwrite an explicitly parsed `NEXT_ACTION: PROBE`.
  - Repro (unit):
    - `python - <<'PY'
from xyzgl.orchestrator.parsing import parse_eval_block
t = "EVAL: Almost there — do not close_node yet.\nGAPS: missing definition\nNEXT_ACTION: PROBE\nQ2: What is arc length?"
print(parse_eval_block(t))
PY`
    - Expected: `next_action` stays `PROBE`.
    - Actual: `next_action` becomes `CLOSE_NODE`.
  - Integration fracture: tiny wording changes (adding/removing the token `close_node` in the tutor’s explanation) can flip whether the orchestrator closes the node, creating a classic “observer-effect” Heisenbug.



## ISSUE-20260205-022 — Float boundary poisoning across replays (NaN/Inf oscillation)
[AFM: AX5, AX11]

- **Boundary trigger:** NaN/Infinity enters artifacts (from corrupted inputs, floating math, or permissive JSON parsing).
- **Evidence:** canonical JSON helpers (`tools/json_canon.py:dumps_canonical`) use stdlib `json.dumps(...)` defaults (allows NaN/Infinity). Multiple validators rely on numeric comparisons that NaN can bypass (e.g., range checks of `<0` / `>1`).
- **Impact:** artifacts become non-standard JSON (many strict parsers reject them). Replays/diffs that hash JSON may diverge across runtimes or languages when NaN/Inf is normalized differently, causing false FAILs and brittle pipelines.
- **Repro:** insert `NaN` into an artifact field (e.g., `confidence`) and run validators; observe inconsistent behavior and potential parse failures in strict JSON environments.
- **Workaround:** set `allow_nan=False` for canonical dumps and explicitly fail on NaN/Inf during schema validation.

## ISSUE-20260205-021 — Retry amplification under partial network failure
[AFM: AX10, AX11]

- **Boundary trigger:** tutor backend intermittently fails (network down, host unreachable) while sessions are configured for many turns.
- **Evidence:** `xyzgl/orchestrator/session_loop.py:run_session()` catches backend exceptions per-turn, records an `ERROR:` reply, and **continues** to subsequent turns without backoff/abort.
- **Impact:** under a failing backend, the system can generate a large number of repeated failing requests (and large `session_report.json`), amplifying load and producing huge artifacts; with extreme `--max-turns` this behaves like an unbounded retry loop.
- **Repro:** set `DAEDALUS_TUTOR_BACKEND=ollama` and `DAEDALUS_OLLAMA_HOST` to an unreachable host; run `python tools/harness_session.py --issue ISSUE-20260205-021 --max-turns 200` and observe repeated per-turn errors.
- **Workaround:** abort session after N consecutive backend failures, add exponential backoff, or downgrade to INCOMPLETE early with a single preserved diagnostic.

## ISSUE-20260205-020 — Symlink + Zip overlay chain escape
[AFM: AX6, AX11]

- **Boundary trigger:** overlay archive contains a symlink entry (or path traversal) and the overlay apply tool runs on a platform where symlinks are materialized on extract.
- **Evidence:** `tools/apply_signal_fidelity_overlay.py` uses `zipfile.ZipFile(...).extractall(tmp_dir)` (no zip-slip protection). It then iterates extracted files via `Path.rglob()` and copies with `shutil.copy2(...)` (default `follow_symlinks=True`).
- **Impact:** an attacker-controlled overlay could cause reading arbitrary files outside `tmp_dir` via symlink targets and copy their contents into repo-root `signal_fidelity_src/` (data exfiltration / unexpected inclusion).
- **Repro (Unix):** create a zip containing a symlink (e.g., link `leak` -> `/etc/passwd`) and run:
  - `python tools/apply_signal_fidelity_overlay.py --issue ISSUE-20260205-020`
  - Observe `signal_fidelity_src/leak` containing the symlink target’s contents.
- **Workaround:** reject symlinks on extract/copy; implement zip-slip path normalization; copy with `follow_symlinks=False` and/or verify realpaths remain under the extracted root.

## ISSUE-20260205-019 — Witness memory balloon at 99.9% RAM
[AFM: AX10, AX11]

- **Boundary trigger:** very large exception payloads or large nested objects passed into Witness event capture.
- **Evidence:** `witness/core.py:WitnessCore._to_jsonable()` converts arbitrary objects/collections into JSON-friendly structures but does **not** cap string lengths; `write_event_json()` builds a full JSON string in memory via `json.dumps(...)` before writing.
- **Impact:** large payloads can cause multi-GB transient memory spikes (payload + json string), leading to OOM or severe swapping right when the system is already failing (worst-time amplification).
- **Repro (synthetic):** create a payload with a multi-hundred-MB string/list and call `WitnessCore.make_event(...)` + `write_event_json(...)`.
- **Workaround:** enforce maximum string/collection byte budgets during `_to_jsonable`, stream JSON writing, and/or store large blobs as external files with hashes.

## ISSUE-20260205-018 — Partial-write artifacts misclassified as valid
[AFM: AX2, AX11]

- **Boundary trigger:** disk at 99.9% full, process kill, or crash mid-write (torn/truncated JSON).
- **Evidence:** `tools/json_canon.py:write_json()` uses `Path.write_text()` directly (non-atomic), so a partial file can be left behind if interrupted.
- **Impact:** downstream tools that `json.loads()` these artifacts can crash (or mark runs INCOMPLETE) and leave empty run dirs if they allocate before parsing; false “valid file exists” checks become possible.
- **Repro:** fill disk / simulate interruption while writing a large report JSON; confirm a truncated JSON file exists and downstream tools fail to parse it.
- **Workaround:** atomic write (temp file + fsync + rename) for JSON artifacts; optionally add a checksum footer or `*.tmp` staging convention.

## ISSUE-20260205-017 — Clock-skew replay divergence (time.time vs monotonic assumptions)
[AFM: AX1, AX11]

- **Boundary trigger:** system clock moves backward/forward (NTP adjustment, VM suspend/resume) while measuring latency with `time.time()`.
- **Evidence:** multiple backends measure latency via `int((time.time() - t0) * 1000)` (e.g., `xyzgl/backends/gemini.py`, `xyzgl/backends/ollama.py`) and tools compute run IDs from wall clock (e.g., `tools/mirror_leakage_detector.py:_run_id`).
- **Impact:** negative/unstable `latency_ms` can appear; any tooling that hashes/compares full turn structures (or enforces non-negative latency) can show false diffs or fail contracts, even when replies are identical.
- **Repro:** on a machine where you can adjust time, run a session using an HTTP backend, then adjust the clock backward during a request; observe `latency_ms` anomalies in `session_report.json` and downstream validator behavior.
- **Workaround:** prefer monotonic clocks for elapsed time, and exclude timing fields from equality/hash comparisons used for determinism checks.

## ISSUE-20260205-016 — Path-length overflow breaks Windows replays
[AFM: AX2, AX10, AX11]

- **Boundary trigger:** deep run bundle nesting (e.g., `runs/<run_id>/child_runs/...`) plus long `DAEDALUS_RUNS_DIR` and/or long `run_id` / issue IDs on Windows (MAX_PATH).
- **Evidence:** run directories are created via `tools/run_paths.py:allocate_run_dir()` without any path-length guard or fallback; several tools create nested children (e.g., `tools/repro_replay_diff.py` writes `child_runs/replay_<id>/...`).
- **Impact:** `OSError: [WinError 206] The filename or extension is too long` (or similar) can occur **after** a run dir is allocated, leaving an empty/partial bundle (audit gap).
- **Repro (Windows):**
  1. Set `DAEDALUS_RUNS_DIR` to a very deep path (e.g., a long user profile path + nested folders).
  2. Run replay which nests child runs:
     - `python tools/repro_replay_diff.py runs/<some_run_id> --issue ISSUE-20260205-016`
  3. Observe failures creating/writing within `child_runs/` once path length crosses the OS limit.
- **Workaround:** keep `DAEDALUS_RUNS_DIR` short (e.g., `C:\runs`) and avoid long `--run-id` values; prefer shallow child run layouts.

## ISSUE-20260205-047 — repro_replay_diff reground cadence inference can create false FAILs
[AFM: AX1, AX11]

- **Boundary trigger:** original run uses `protocol_reground_every <= 0` (reground only on turn 0) or uses a cadence larger than the observed turn span; replay infers the wrong cadence.
- **Evidence:** `tools/repro_replay_diff.py:_replay_session()` infers `every` by looking at observed `protocol_regrounded` turns; if only turn 0 is regrounded, it falls back to `every = 5`.
- **Impact:** replay can reground at turns 5,10,… even when the original did not, changing prompts and replies and producing a mismatch in `stable_hash` (false regression).
- **Repro:**
  1. Run a session with reground disabled after turn 0: `DAEDALUS_PROTOCOL_REGROUND_EVERY=0 python tools/harness_session.py --issue ISSUE-20260205-047 --max-turns 12`
  2. Run replay diff on that run dir: `python tools/repro_replay_diff.py runs/<run_id> --issue ISSUE-20260205-047`
  3. Observe replay regrounds at turn 5+ and hashes diverge.
- **Workaround:** store the effective config in `session_report.json` (or in `run.json`) and replay from that, instead of inference; or treat timing/meta fields as non-semantic in the hash.

## ISSUE-20260205-048 — prompt_snapshot_guard writes baseline before report; read-only FS causes empty runs
[AFM: AX1, AX2, AX7, AX11]

- **Boundary trigger:** baseline missing and repo is read-only (CI, packaged archive, or restrictive permissions).
- **Evidence:** `tools/prompt_snapshot_guard.py` writes the baseline to `snapshots/prompt_snapshots.json` when `not baseline` even if `--update` is **not** set, and it performs this write **before** writing the run-bundle report files.
- **Impact:**
  - In read-only environments, the tool can crash after allocating `run_dir` but before writing `prompt_snapshot_report.json`/`run.json` → empty bundle (audit gap).
  - `run.json` sets `deterministic: True` when `--update` is false, even though the run may mutate the repo by creating the baseline.
- **Repro:** remove `snapshots/prompt_snapshots.json` and run in a read-only checkout (or chmod the directory) with `python tools/prompt_snapshot_guard.py --issue ISSUE-20260205-048`.
- **Workaround:** never auto-write baseline unless `--update`; write reports first; mark determinism false whenever baseline writes occur.

## ISSUE-20260205-049 — secret_scanner can crash on PermissionError/OSError in _is_text
[AFM: AX2, AX11]

- **Boundary trigger:** scanning a tree containing unreadable files, broken mount points, or special permission bits (common in containerized or constrained environments).
- **Evidence:** `tools/secret_scanner.py:_is_text()` calls `path.stat().st_size` without a try/except. If `stat()` raises, the whole scan aborts.
- **Impact:** tool can exit with an unhandled exception after allocating `run_dir`, producing an empty/partial run bundle and skipping the secret scan (audit gap).
- **Repro:** point `--path` at a directory containing an unreadable file (or chmod 000) and run `python tools/secret_scanner.py --issue ISSUE-20260205-049 --path <dir>`.
- **Workaround:** wrap `stat()` in try/except and treat failures as non-text/skip with a recorded note.

## ISSUE-20260205-050 — curriculum_corpus_linter can hang/OOM on huge or special files
[AFM: AX10, AX11]

- **Boundary trigger:** manifest points at very large files or special files (e.g., `/dev/zero`) via path traversal, symlink, or misconfiguration.
- **Evidence:** `tools/curriculum_corpus_linter.py` reads each candidate with `Path.read_text(encoding='utf-8')` to validate UTF-8 and compute hashes, with no max-byte budget and no special-file guard.
- **Impact:** on special files with no EOF (or very large files), the linter can hang indefinitely or exhaust memory, frequently **before** producing run artifacts.
- **Repro (Unix):** include a corpus entry that resolves to `/dev/zero` (or a multi-GB file) and run `python tools/curriculum_corpus_linter.py --issue ISSUE-20260205-050 --mode local`.
- **Workaround:** enforce a strict max-bytes cap and reject non-regular files; stream decoding instead of `read_text()`.

## ISSUE-20260205-051 — apply_signal_fidelity_overlay vulnerable to zip bombs / unbounded extraction
[AFM: AX6, AX10, AX11]

- **Boundary trigger:** attacker-controlled overlay archive with extreme compression ratio (zip bomb) or huge extracted size.
- **Evidence:** `tools/apply_signal_fidelity_overlay.py` uses `ZipFile.extractall(tmp_dir)` with no limits on file count, total extracted bytes, or compression ratio.
- **Impact:** disk exhaustion (or huge runtime) during extraction, potentially destabilizing the host and leaving partial run bundles; worst-case causes denial of service during “overlay apply.”
- **Repro:** create a zip bomb (or a zip containing many large files) and run `python tools/apply_signal_fidelity_overlay.py --issue ISSUE-20260205-051` pointing `signal_fidelity_overlay.zip` at it.
- **Workaround:** enforce max archive size, max extracted bytes, max file count, and compression-ratio checks before extraction.

## ISSUE-20260205-052 — apply_signal_fidelity_overlay marks deterministic=True but uses wall-clock run_id
[AFM: AX1, AX11]

- **Boundary trigger:** any run; determinism claim is inconsistent with implementation.
- **Evidence:** `tools/apply_signal_fidelity_overlay.py` sets `deterministic: True` in both the report and `run.json`, but `run_id` is computed from `time.time()` (wall clock). External extractors (rar/unzip) also introduce nondeterministic timestamps/orderings.
- **Impact:** repeated runs with the same inputs do not produce byte-identical artifacts; deterministic gating can be misled.
- **Repro:** run the tool twice with the same overlay source and compare `signal_fidelity_apply_report.json`/`run.json` (different `run_id`).
- **Workaround:** set determinism false (or compute run_id deterministically from inputs), and record extractor nondeterminism explicitly.

## ISSUE-20260205-053 — mirror_leakage_detector can crash on malformed session_report.json after allocating run_dir
[AFM: AX2, AX11]

- **Boundary trigger:** non-UTF8 session report, torn JSON, or unexpected types in `turn_index` (string/non-numeric).
- **Evidence:** `tools/mirror_leakage_detector.py` allocates `run_dir` and then calls `json.loads(fp.read_text(encoding='utf-8'))` (no guard). It also does `tid = int(...turn_index...)` without try/except.
- **Impact:** unhandled `UnicodeDecodeError` / `JSONDecodeError` / `ValueError` causes a crash and leaves an empty run bundle (audit gap) exactly when artifacts are already corrupted.
- **Repro:** corrupt `session_report.json` (truncate mid-file or set `turn_index` to `'x'`) and run `python tools/mirror_leakage_detector.py <path> --issue ISSUE-20260205-053`.
- **Workaround:** parse/decode guards that write an INCOMPLETE report inside `run_dir` even on failures; validate types per schema.

## ISSUE-20260205-054 — router clamp behaves unexpectedly for negative max_chars
[AFM: AX11]

- **Boundary trigger:** `max_chars_in` or `max_chars_out` configured as a negative integer (e.g., via programmatic config or malformed config dict).
- **Evidence:** `xyzgl/router.py:_clamp(s, n)` returns `s[:n]` when `len(s) > n`. With `n < 0`, Python slicing drops the last `abs(n)` characters instead of yielding empty/disabled behavior.
- **Impact:** a negative clamp can silently pass almost the entire string through (minus a few chars), defeating size budgets and producing confusing “nearly full prompt” behavior at boundary configs.
- **Repro:** call `route_turn(..., cfg=XYZGLConfig(... max_chars_in=-1 ...))` and observe input is only missing its last character.
- **Workaround:** treat `n <= 0` as “empty” (or as “no clamp”, but explicitly) and validate config on construction.


- ISSUE-20260205-055 [AFM: AX10, AX11]
  - Symptom: `tools/mirror_calibration_bench.py` can become extremely slow (or appear “hung”) and/or spike memory when mirror/user answers are very large (MB-scale).
  - Micro-cause: it lowercases whole strings and then runs `difflib.SequenceMatcher(...).ratio()`:
    - `a=(mirror or "").lower()` and `b=(user or "").lower()` duplicate large strings in memory.
    - `SequenceMatcher` can be O(n^2) time/memory in worst cases, so very long inputs can blow up.
  - Boundary trigger: “MAX” outputs (very long answers), or memory already ~99.9% full.
  - Repro (synthetic):
    - `python - <<'PY'
import json, pathlib
p = pathlib.Path("tmp_big_session_report.json")
big = "x" * 2_000_000  # 2MB
doc = {"schema_version":"session_report@1","turns":[{"turn_index":0,"mirror":{"answer":big},"eval":{"user_answer":big}}]}
p.write_text(json.dumps(doc), encoding="utf-8")
print("wrote", p, "bytes", p.stat().st_size)
PY`
    - Then: `python tools/mirror_calibration_bench.py tmp_big_session_report.json --issue ISSUE-20260205-055`
  - Expected: hard cap / truncation per field before similarity metrics; tool should still write a FAIL/INCOMPLETE bundle.
  - Observed: heavy CPU/memory; can stall or be killed before producing the report.

- ISSUE-20260205-056 [AFM: AX10, AX11]
  - Symptom: `witness.core.scrub_pii()` can crash with `RecursionError` or loop effectively forever when given cyclic or extremely deep payloads, preventing crash artifacts from being written.
  - Micro-cause: `scrub_pii()` recursively walks dict/list without cycle detection or depth limits; cycles (self-references) never terminate.
  - Boundary trigger: payload contains a self-reference (cycle) or very deep nesting (approaching Python recursion limit).
  - Repro (unit):
    - `python - <<'PY'
import sys
sys.path.insert(0,".")
from witness.core import WitnessCore
p = {}
p["self"] = p   # cycle
wc = WitnessCore()
wc.make_event("ISSUE-20260205-056", p)
print("unreachable")
PY`
  - Expected: detect cycles / enforce max depth and replace with `"<cycle>"` / `"<max_depth>"`, then still write a valid witness event.
  - Observed: recursion crash; no event output (audit gap) if this occurs in a harness path.

- ISSUE-20260205-057 [AFM: AX2, AX11]
  - Symptom: `tools/protocol_drift_radar.py` can crash on schema drift/corruption (e.g., non-numeric `turn_index`) after allocating a run dir, leaving an empty bundle.
  - Micro-cause: in `_collect_texts(session_report.json)` it does `ti = int(t.get("turn_index") or 0)` with no try/except and no fallback for bad types.
  - Boundary trigger: torn/corrupted JSON or schema drift where `turn_index` is `"x"` / `null` / dict.
  - Repro:
    1) Create a minimal `tmp_bad_turn_index.json` with `turn_index: "x"`.
    2) Run: `python tools/protocol_drift_radar.py tmp_bad_turn_index.json --issue ISSUE-20260205-057`
  - Expected: tool should record `problems[]` and return INCOMPLETE while still writing its report bundle.
  - Observed: unhandled `ValueError` aborts execution; run dir may exist but is missing the report.

- ISSUE-20260205-058 [AFM: AX2]
  - Symptom: `tools/issue_id.py:validate_issue_id()` accepts impossible dates and out-of-range values because it only checks a regex.
  - Micro-cause: regex-only validation (`^ISSUE-\d{8}-\d{3}$`) does not verify calendar validity (month/day) or reasonable ranges.
  - Boundary trigger: “nonsense” IDs that still match regex, e.g. `ISSUE-20260299-999`, `ISSUE-00000000-000`.
  - Repro: `python tools/harness_turn.py --issue ISSUE-20260299-001`
  - Expected: reject invalid calendar dates (and optionally enforce NNN range policy).
  - Observed: accepted; downstream sorting / audit-by-date can become misleading.

- ISSUE-20260205-059 [AFM: AX2, AX11]
  - Symptom: whitespace-padded issue IDs can pass validation but be written **with whitespace** into artifacts, causing subtle mismatches across tools/docs.
  - Micro-cause: `validate_issue_id()` checks `issue_id.strip()` against the regex but tools keep using the original unstripped string (`args.issue`) in `run.json` and reports.
  - Boundary trigger: CLI argument includes trailing/leading spaces (common in copy/paste).
  - Repro:
    - `python tools/harness_turn.py --issue "ISSUE-20260205-059 "`
    - Inspect the resulting `run.json` / report: `issue_id` includes a trailing space.
  - Expected: normalize (strip) the value once validated and use the normalized form everywhere.
  - Observed: “valid but inconsistent” IDs across bundles and doc references.

- ISSUE-20260205-060 [AFM: AX10, AX11]
  - Symptom: several “artifact-reading” tools can OOM or stall when given extremely large JSON artifacts because they read the entire file into memory before any filtering.
  - Concrete example: `tools/protocol_drift_radar.py:_load_json()` does `json.loads(p.read_text(...))` (unbounded).
  - Boundary trigger: session reports that grow very large (high `--max-turns`, large excerpts, or repeated backend failures) or low-memory environments (~99.9% full).
  - Repro (synthetic): generate a multi-hundred-MB JSON file and run `protocol_drift_radar` (or similar tool) on it; observe memory spike / crash before any report is written.
  - Expected: enforce max-bytes limits (or stream / incremental parse) and still write an INCOMPLETE report bundle.
  - Observed: process can be killed or crash before producing artifacts (audit gap).


- ISSUE-20260205-061 [AFM: AX2, AX11]
  - Symptom: `tools/doc_code_link_checker.py` can raise `JSONDecodeError` (or `UnicodeDecodeError`) when loading `docs/AI_INDEX.json`, **after** it already allocated `runs/<run_id>/` → leaves an empty run dir / no report.
  - Micro-cause: `_load_json()` is `json.loads(p.read_text(encoding='utf-8'))` with no try/except; `doc = _load_json(ai_index_path)` runs after `run_dir = allocate_run_dir(run_id)`.
  - Boundary trigger: partially-written AI_INDEX (torn write, disk nearly full), or non-UTF8 bytes.
  - Expected: record the parse failure in `problems[]` and still write `doc_link_report.json` + `run.json` (FAIL/INCOMPLETE) so CI has an audit trail.
  - Evidence:
    - File: `tools/doc_code_link_checker.py`
    - Snippet: `_load_json(p): return json.loads(p.read_text(encoding='utf-8'))`

- ISSUE-20260205-062 [AFM: AX2, AX11]
  - Symptom: `tools/reground_cadence_verifier.py` can throw `ValueError` on `int(tr.get('turn_index', -1))` and abort **after** `out_dir` is created → empty bundle / audit gap.
  - Micro-cause: In the session_turns path it does `ti = int(tr.get('turn_index', -1))` with no per-item try/except; this occurs after `out_dir = allocate_run_dir(run_id)`.
  - Boundary trigger: schema drift or corrupted `session_report.json` where `turn_index` is non-int-convertible (e.g. `"x"`, `null`, `"0x10"`).
  - Expected: treat bad `turn_index` as a problem, continue, and write a FAIL/INCOMPLETE bundle.
  - Evidence:
    - File: `tools/reground_cadence_verifier.py`
    - Snippet: `for tr in turns: ti = int(tr.get('turn_index', -1))`

- ISSUE-20260205-063 [AFM: AX5, AX10, AX11]
  - Symptom: `tools/atheris_fuzz_router.py` derives `cases = max(1, args.seconds) * 200` for the deterministic fallback fuzzer; with extreme `--seconds` (MAX_INT) this becomes an effectively unbounded loop, generating massive random byte blobs and invoking `route_turn` billions of times.
  - Micro-cause: no upper bound / budget gate on `args.seconds`; `cases` is fully materialized as an integer and then used in `for _i in range(cases)`.
  - Boundary trigger: `--seconds 2147483647` or larger; also a small number on very slow machines (infinite-latency equivalent).
  - Expected: clamp seconds/cases to a safe ceiling (or use a time budget with monotonic clock) and always write a bundle that records the clamp.
  - Evidence:
    - File: `tools/atheris_fuzz_router.py`
    - Snippet: `cases = max(1, int(args.seconds)) * 200` then loop over `range(cases)`

- ISSUE-20260205-064 [AFM: AX5, AX10, AX11]
  - Symptom: `tools/seed_sweep.py` iterates `for s in range(seed_start, seed_end+1)` and stores per-seed `samples` + `reply_texts` + `latencies` in memory. With extreme ranges this can consume huge CPU and RAM (and hammer the backend).
  - Micro-cause: no limit on `(seed_end - seed_start)`; all samples are retained in Python lists; each iteration calls `route_turn(...)`.
  - Boundary trigger: `--seed-start 1 --seed-end 10000000` (or worse), or accidentally swapped values with a large absolute difference.
  - Expected: require an explicit `--max-seeds` cap, stream results to disk, or fail fast with an explanatory error.
  - Evidence:
    - File: `tools/seed_sweep.py`
    - Snippet: unbounded `for s in range(...)` + `samples.append(...)`

- ISSUE-20260205-065 [AFM: AX5, AX10, AX11]
  - Symptom: `tools/harness_lattice.py` runs a full cartesian product over `seeds × processes × thicknesses × defects` and stores every case (including full reply text) in memory; large lists explode runtime and can OOM.
  - Micro-cause: nested loops with no cap and `cases.append(CaseResult(... reply=...))`; report then serializes full `cases` array.
  - Boundary trigger: user supplies very long CSV lists (hundreds/thousands of items) or a large defect corpus; memory already pressured (~99.9% full).
  - Expected: enforce a max-case budget (or stream cases), and write only summaries by default with an option to include full cases.
  - Evidence:
    - File: `tools/harness_lattice.py`
    - Snippet: nested loops over four lists; retains `cases` then serializes `cases: [...]`

- ISSUE-20260205-066 [AFM: AX2, AX11]
  - Symptom: `tools/graph_invariant_checker.py` can crash on malformed `knowledge_graph.json` or `session_report.json` (torn write / non‑UTF8 / schema drift) **after** creating `runs/<run_id>/`, leaving an empty bundle (audit gap).
  - Micro-cause:
    - `_load_json()` is `json.loads(p.read_text(encoding="utf-8"))` with no try/except.
    - When `session_report.json` exists, it does `max([int(t.get("turn_index", -1)) for t in turns] ...)` which can throw `ValueError` on non-numeric `turn_index`.
  - Boundary trigger: disk ~99.9% full (torn JSON), interrupted writes, or schema drift where `turn_index` is `"x"`/`null`/dict.
  - Repro:
    1) Create a fake run dir with a truncated `knowledge_graph.json`.
    2) Run: `python tools/graph_invariant_checker.py runs/<fake_run> --issue ISSUE-20260205-066`
    3) Observe unhandled exception and an empty `runs/<new_run_id>/`.
  - Expected: write an INCOMPLETE report + `run.json` even when inputs are unreadable, so the failure is auditable.
  - Evidence: `tools/graph_invariant_checker.py` — `_load_json()` and the `max([int(...turn_index...) ...])` list comprehension.

- ISSUE-20260205-067 [AFM: AX2, AX10, AX11]
  - Symptom: `tools/coverage_gate.py` can crash while loading `coverage_raw.json` (produced by `coverage.py`) if the JSON report is truncated/corrupted (common when disk is nearly full), leaving a partial/empty run bundle.
  - Micro-cause: after `cov.json_report(outfile=...)`, it does `raw = json.loads(raw_path.read_text(..., errors="replace"))` with no try/except; a torn JSON file triggers `JSONDecodeError`.
  - Boundary trigger: disk ~99.9% full during `coverage_raw.json` write, process interruption, or extremely large coverage JSON.
  - Repro (fault injection):
    - Run `python tools/coverage_gate.py --issue ISSUE-20260205-067`, then manually truncate `runs/<run_id>/coverage_raw.json` before the `json.loads` step (or simulate disk-full).
  - Expected: catch decode errors, emit INCOMPLETE with a report that includes the decode failure.
  - Evidence: `tools/coverage_gate.py` — `cov.json_report(...)` then `json.loads(raw_path.read_text(...))`.

- ISSUE-20260205-068 [AFM: AX10, AX11]
  - Symptom: HTTP backends can spike memory or stall when the server returns an unusually large response body (no max-bytes guard).
  - Micro-cause: `xyzgl/util_http.py:post_json()` does `raw = resp.read().decode("utf-8")` (reads the entire body into RAM) before parsing.
  - Boundary trigger: misbehaving backend / proxy returning a huge payload (or repeated error payloads), especially when memory is already constrained.
  - Repro: point `DAEDALUS_OLLAMA_HOST` to an endpoint that returns a very large body for `/api/generate`, then run any session using the ollama backend.
  - Expected: enforce a max response size (or stream) and fail fast with a bounded error.
  - Evidence: `xyzgl/util_http.py` — `resp.read()` with no size cap.

- ISSUE-20260205-069 [AFM: AX11]
  - Symptom: HTTP backends can crash with an unwrapped `UnicodeDecodeError` if the server returns non‑UTF8 bytes, bypassing `HTTPError` handling and causing tool/session aborts without a clean backend error message.
  - Micro-cause: `post_json()` decodes with `decode("utf-8")` and only catches `urllib.error.*` + `socket.timeout`; decode failures are not caught/wrapped.
  - Boundary trigger: gateway/proxy returning binary error pages, corrupted bytes, or charset mismatch.
  - Repro: point the backend host at an endpoint that returns invalid UTF‑8 bytes, then call `post_json()` via `gemini` or `ollama`.
  - Expected: catch decode failures and raise `HTTPError("Invalid UTF-8 response ...")` (or decode with `errors="replace"` and treat as parse failure).
  - Evidence: `xyzgl/util_http.py` — `resp.read().decode("utf-8")` outside any decode-error guard.

- ISSUE-20260205-070 [AFM: AX2, AX11]
  - Symptom: `tools/ontario_claims_citation_guard.py` can crash on malformed JSON or non-numeric `turn_index` **after** allocating `runs/<run_id>/`, leaving an empty bundle (audit gap).
  - Micro-cause:
    - `outer = json.loads(fp.read_text(encoding="utf-8"))` has no try/except.
    - For session reports it does `tid = int((t or {}).get("turn_index") or 0)` with no guard.
  - Boundary trigger: torn/corrupt report JSON, non-UTF8 bytes, or schema drift where `turn_index` is `"x"`.
  - Repro: set `turn_index` to `"x"` in a session report and run `python tools/ontario_claims_citation_guard.py <path> --issue ISSUE-20260205-070`.
  - Expected: emit an INCOMPLETE report bundle recording the parse/type failure.
  - Evidence: `tools/ontario_claims_citation_guard.py` — `json.loads(read_text(...))` + `tid = int(...)`.

- ISSUE-20260205-071 [AFM: AX2, AX10, AX11]
  - Symptom: runner-style tools can **hang indefinitely** (infinite latency) or spike RAM when a subcommand stalls or prints huge output.
  - Micro-cause: multiple tools use `subprocess.run(..., capture_output=True)` with **no timeout** and with full stdout/stderr captured into memory (truncation happens only *after* capture).
  - Affected tools (examples):
    - `tools/ci_gate.py` → `_run_step()` uses `subprocess.run(..., capture_output=True)` (no timeout).
    - `tools/targeted_sweep.py` → `_step()` uses `subprocess.run(..., capture_output=True)` (no timeout).
    - `tools/mutation_suite.py` → `_run_cmd_capture()` uses `subprocess.run(..., capture_output=True)` (no timeout).
  - Boundary trigger:
    - A sub-tool deadlocks / waits on I/O (infinite latency).
    - A sub-tool prints extremely large output (memory blow even though stdout is later “tailed”).
  - Repro (hang):
    - Replace any step command with a never-ending program (e.g., `python -c "import time; time.sleep(10**9)"`) and observe the parent tool never completes.
  - Expected: enforce a per-step timeout and stream output (or cap bytes read) so the tool always writes a FAIL/INCOMPLETE bundle.
  - Evidence:
    - `tools/ci_gate.py`: `p = subprocess.run(cmd, text=True, capture_output=True, env=env)`
    - `tools/targeted_sweep.py`: `p = subprocess.run(cmd, text=True, capture_output=True, env=env)`
    - `tools/mutation_suite.py`: `p = subprocess.run(cmd, cwd=str(_REPO_ROOT), text=True, capture_output=True)`

- ISSUE-20260205-072 [AFM: AX2, AX11]
  - Symptom: the crash-to-report core (`WitnessCore.make_event`) can raise `TypeError` and fail to produce an event when payload values are not JSON-serializable.
  - Micro-cause: event-id derivation calls `_stable_json(payload)` which is `json.dumps(...)` with no default encoder; `scrub_pii()` preserves non-JSON types (e.g., `set`, `bytes`, `Path`, custom objects).
  - Boundary trigger: payload includes non-JSON types (common in “crash context” objects).
  - Repro:
    - `python -c "from witness.core import WitnessCore; print(WitnessCore().make_event('ISSUE-20260205-072', {'bad': set([1,2])}))"`
  - Expected: witness should *always* emit an event (e.g., lossy stringify for unknown types) so audit artifacts exist even under chaos.
  - Evidence: `witness/core.py` — `_stable_json(obj) -> json.dumps(...)` then `_event_id(... _stable_json(payload) ...)`.

- ISSUE-20260205-073 [AFM: AX5, AX11]
  - Symptom: `tools/property_turn_fuzzer.py` can report **PASS with zero tests run**.
  - Micro-cause: `--cases` is not validated; `range(cases)` with a negative value runs zero iterations, leaving `problems=[]`, so `overall="PASS"`.
  - Boundary trigger: `--cases 0` or `--cases -1` (bad CLI input; copy/paste mistakes).
  - Repro:
    - `python tools/property_turn_fuzzer.py --issue ISSUE-20260205-073 --cases -1 --max-len 80`
  - Expected: treat non-positive cases as FAIL/INCOMPLETE with an explicit message, or clamp to a minimum.
  - Evidence: `tools/property_turn_fuzzer.py` — `for i in range(cases): ...` then `overall = "PASS" if not problems else "FAIL"`.

- ISSUE-20260205-074 [AFM: AX5, AX11]
  - Symptom: `tools/seed_sweep.py` can report **PASS with an empty seed range**.
  - Micro-cause: the loop is `for s in range(seed_start, seed_end + 1)` with no validation that `seed_end >= seed_start`; if swapped, the loop runs zero times and `unique_replies=0`, which passes the threshold check.
  - Boundary trigger: user supplies reversed bounds (common mistake), e.g. `--seed-start 5 --seed-end 1`.
  - Repro:
    - `python tools/seed_sweep.py --issue ISSUE-20260205-074 --seed-start 5 --seed-end 1`
  - Expected: reject reversed/empty ranges (or auto-swap) and record the condition in the report.
  - Evidence: `tools/seed_sweep.py` — `for s in range(args.seed_start, args.seed_end + 1): ...`

- ISSUE-20260205-075 [AFM: AX11]
  - Symptom: HTTP wrapper can raise an unwrapped `TypeError` before any network call if the payload contains non-JSON-serializable objects.
  - Micro-cause: `xyzgl/util_http.py:post_json()` does `json.dumps(payload, ...)` but only catches `HTTPError/URLError/socket.timeout` and `JSONDecodeError`; `TypeError` from `json.dumps` is not wrapped.
  - Boundary trigger: backend callers accidentally pass sets/bytes/custom objects inside the payload dict.
  - Repro (no network required; fails before request):
    - `python -c "from xyzgl.util_http import post_json; post_json('http://localhost:1', {'x': set([1,2])})"`
  - Expected: catch serialization errors and raise a consistent `HTTPError` (or a dedicated error type) so callers can treat it as a backend failure.
  - Evidence: `xyzgl/util_http.py` — `data = json.dumps(payload, ensure_ascii=False).encode('utf-8')` with no guard.
