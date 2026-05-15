# XYZGL Master Bug Report - Final Unified (v27 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v26_20260309_113422.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-09_run27.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round74.md`
- `c:\Users\misha\Downloads\BUGPACK_v15.1_20260309_153121.zip`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round46.md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260309_fresh25.zip`
- `c:\Users\misha\Downloads\round47_new_replay_protocol_bugs.zip`
- `c:\Users\misha\Downloads\new_bug_save_graph_truncates_node_ids_and_causes_collisions_package.zip`
- `c:\Users\misha\Downloads\round20_pass10_rebuilt_bug_bundle.zip`

This v27 addendum supersedes the v26 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v26 master: 147
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 8 groups
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 149

New defect IDs added here:
- `BUG-148`
- `BUG-149`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `new_bugs_grouped_by_file_2026-03-09_run27.md`
- `XYZGL_new_bug_report_round74.md`
- `session_state_nondeterminism_findings_round46.md`
- `xyzgl_bug_findings_20260309_fresh25.zip`
- `round47_new_replay_protocol_bugs.zip`
- `new_bug_save_graph_truncates_node_ids_and_causes_collisions_package.zip`
- `round20_pass10_rebuilt_bug_bundle.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v15.1_20260309_153121.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v27

### BUG-148: `save_graph()` truncates `node_id`, so distinct long node identities can collide and merge on reload

- **Severity:** High
- **Phase:** 2
- **Source:** `new_bug_save_graph_truncates_node_ids_and_causes_collisions_package.zip`
- **Affected file:**
  - `xyzgl/knowledge/graph.py`

**Problem:** `save_graph()` persists `node_id` through `_safe_text(..., max_chars=MAX_TOKEN_CHARS)`, truncating identity keys to 80 characters. Two distinct node IDs that differ only after the first 80 characters are therefore written out with the same persisted `node_id`. On reload, `load_graph()` keys by that truncated ID and merges the two rows through `_merge_nodes(...)`, silently collapsing graph structure and destructively combining fields such as `required_keywords` and `confidence`. In the supplied repro, a mastered node and an unmastered node reload as one merged node with downgraded confidence.

**Expected:** `node_id` is a lossless identity field. Persistence should preserve the full ID or reject oversize IDs explicitly; it must not silently truncate keys and let reload merge distinct nodes.

**Fix:** Stop truncating `node_id` during persistence. If a hard maximum is required, validate and fail fast on oversize IDs instead of clipping them. Add a save/load round-trip guard that rejects identity-colliding persisted graphs.

### BUG-149: some tools write `run.json.seed = 1337` even though their CLI does not expose any seed input, so the artifact claims non-auditable provenance

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_grouped_by_file_2026-03-09_run27.md`
- **Affected files:**
  - `tools/doc_code_link_checker.py`
  - `tools/mutation_suite.py`

**Problem:** These tools hard-seed internal randomness to `1337` and then write `"seed": 1337` into `run.json`, but their public CLI exposes no `--seed` argument and no equivalent user-controlled seed contract. The saved artifact therefore claims seed provenance that the caller cannot select, vary, or verify as an input. This overstates reproducibility metadata and makes the bundle look as though `seed` were part of the external execution contract when it is only an internal implementation constant.

**Expected:** If `run.json` records a seed, that seed should be part of the tool's actual caller-controlled contract and help reproduce the run. Otherwise the field should be omitted or replaced with metadata that clearly distinguishes internal fixed constants from user inputs.

**Fix:** Either add an explicit `--seed` interface and persist the effective seed, or stop writing a misleading `seed` field for tools whose seed is not externally configurable.

## Existing Bug Enrichments Added In v27

### BUG-50 enrichment: session and sweep artifacts still collapse distinct mirror privacy modes into the same saved output

Additional evidence folded into `BUG-50` from `session_state_nondeterminism_findings_round46.md`:
- `harness_session.py` still emits identical session artifacts after normalizing ids even when `DAEDALUS_MIRROR_SEND_USER_CONTENT` flips the live router path between `redacted` and `raw`
- `seed_sweep.py` still records no mirror-side execution details, so raw-vs-redacted mirror runs normalize to the same sweep report

This remains the same mirror privacy-state propagation and artifact-audibility defect already tracked by `BUG-50`.

### BUG-52 enrichment: `seed_sweep.py` can still report a seed that was never actually swept

Additional evidence folded into `BUG-52` from `session_state_nondeterminism_findings_round46.md`:
- `run.json.seed` and `seed_sweep_report.json.seed` can still be `999` while the actual sampled seeds are only `[11, 12]`

This is the same seed-metadata mismatch family already tracked by `BUG-52`.

### BUG-106 enrichment: `secret_scanner.py` still misses more raw token families and credential-bearing DSN/URL forms

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round74.md` and `xyzgl_bug_findings_20260309_fresh25.zip`:
- raw token families still pass for npm tokens, SendGrid keys, Slack user/session/refresh tokens, Azure SAS tokens, and PayPal/Braintree keys
- additional credential-bearing URL/DSN families still pass, including `svn+ssh://`, `scp://`, `git://`, `irc://`, `xmpp://`, `postgresql+psycopg2://`, `mysql+pymysql://`, and `redis+sentinel://`

This remains the same broad secret false-negative family already tracked by `BUG-106`.

### BUG-111 enrichment: turn replay still ignores more recorded control fields such as `seed` and `config.mirror_backend`

Additional evidence folded into `BUG-111` from `round47_new_replay_protocol_bugs.zip`:
- changing stored turn `seed` from `1337` to `9999` still yields `PASS` and `--strict PASS`
- changing stored turn `config.mirror_backend` from `stub` to `ollama` still yields `PASS` and `--strict PASS`

This is the same replay-contract omission family already tracked by `BUG-111`.

### BUG-117 enrichment: session replay still false-fails on inert telemetry that the replay path never consumes

Additional evidence folded into `BUG-117` from `round47_new_replay_protocol_bugs.zip`:
- changing only `session_report.turns[0].eval.prompt_meta.tutor_latency_ms` still forces both non-strict and strict replay to `FAIL`
- the replay path does not consume that telemetry, but the comparer still treats it as behaviorally material by hashing the full exported turns array

This is the same inert-metadata / forward-compatible false-fail family already tracked by `BUG-117`.

### BUG-17 enrichment: protocol drift detection still misses more phrasing, still false-positives some noun phrases, and still ignores `backend_error` text

Additional evidence folded into `BUG-17` from `round47_new_replay_protocol_bugs.zip`:
- `protocol_drift_radar.py` still false-positives ordinary tutor text such as `I am the mirror image ...`
- it still misses lesson framing such as `Today's lesson ...`
- it still ignores role-bearing text when it is stored in turn-level `backend_error`

This remains the same detector narrowness and scanned-field coverage family already tracked by `BUG-17`.

### BUG-81 enrichment: more tools are still emitting non-canonical `run.json` artifacts

Additional evidence folded into `BUG-81` from `round20_pass10_rebuilt_bug_bundle.zip`:
- `redteam_injection_suite.py` still emits a non-canonical `run.json`
- `reground_cadence_verifier.py` still emits a non-canonical `run.json`

This is the same non-canonical run-artifact family already tracked by `BUG-81`.

### BUG-34 enrichment: `property_turn_fuzzer.py` non-canonical `run.json` still reproduces in the rebuilt pass-10 bundle

Additional evidence folded into `BUG-34` from `round20_pass10_rebuilt_bug_bundle.zip`:
- `artifact_roundtrip.py --strict` still fails on a repo-emitted `property_turn_fuzzer.py` bundle because its `run.json` is not canonical

This remains the same non-canonical `property_turn_fuzzer.py` artifact bug already tracked in the master.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v15.1_20260309_153121.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- `session_state_nondeterminism_findings_round46.md` contributed only existing `BUG-50` and `BUG-52` evidence.
- `XYZGL_new_bug_report_round74.md` and `xyzgl_bug_findings_20260309_fresh25.zip` contributed only additional secret-scanner false-negative families for `BUG-106`.
- `round47_new_replay_protocol_bugs.zip` contributed only existing replay-contract and detector-coverage families (`BUG-111`, `BUG-117`, `BUG-17`).
- `round20_pass10_rebuilt_bug_bundle.zip` rebuilt a missing bundle path but only reconfirmed already-tracked non-canonical artifact bugs (`BUG-81`, `BUG-34`).

## Recommended Fix Order For The New Bugs

1. `BUG-148`
2. `BUG-149`

## Preserved Prior Master Body (v26 Combined)
# XYZGL Master Bug Report - Final Unified (v26 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v25_20260309_111941.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-09_run26.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round73.md`
- `c:\Users\misha\Downloads\BUGPACK_v15.0_20260309_150143.zip`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round45.md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260309_fresh24.zip`
- `c:\Users\misha\Downloads\new_bug_session_prompt_meta_unsanitized_leaks_paths_package.zip`
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs21_report.zip`
- `c:\Users\misha\Downloads\new_bugs_round44_bundle.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260309_fresh23.zip`

This v26 addendum supersedes the v25 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v25 master: 145
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 6 groups
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 147

New defect IDs added here:
- `BUG-146`
- `BUG-147`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `new_bugs_grouped_by_file_2026-03-09_run26.md`
- `XYZGL_new_bug_report_round73.md`
- `session_state_nondeterminism_findings_round45.md`
- `xyzgl_bug_findings_20260309_fresh24.zip`
- `new_bug_session_prompt_meta_unsanitized_leaks_paths_package.zip`
- `graph_mirror_round20_newbugs21_report.zip`
- `new_bugs_round44_bundle.zip`
- `xyzgl_bug_findings_20260309_fresh23.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v15.0_20260309_150143.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v26

### BUG-146: session-phase prompt metadata leaks raw absolute paths and unsanitized backend-error details even though `route_turn()` redacts the same fields

- **Severity:** Medium-High
- **Phase:** 1
- **Source:** `new_bug_session_prompt_meta_unsanitized_leaks_paths_package.zip`
- **Affected files:**
  - `xyzgl/router.py`
  - `xyzgl/orchestrator/tutor_phases.py`
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** The one-shot router path sanitizes prompt metadata before returning it, but the phase/session path does not. `route_turn()` redacts `protocol_path` and sanitizes nested grounding metadata, while `_prompt_meta()` in `tutor_phases.py` copies `protocol_path`, `grounding.grounding_dir`, and `backend_error` through verbatim. `SessionReport.to_json()` then exports those raw phase dictionaries directly into `session_report.json`. As a result, absolute local paths and raw backend exception text can leak through session artifacts even though the public turn API would redact the same runtime metadata.

**Expected:** Prompt metadata redaction should be consistent across API surfaces. If `route_turn()` sanitizes path-like fields and backend-error text, session-phase and exported session artifacts should apply the same sanitization policy before serialization.

**Fix:** Move prompt-metadata sanitization into a shared helper and apply it in phase/session export as well as `route_turn()`. Redact or sanitize path-like `protocol_path` and `grounding_dir` values, and clamp/sanitize `backend_error` before it reaches `session_report.json`.

### BUG-147: `targeted_sweep.py` accepts a top-level `--seed` but silently runs a mixed-seed child bundle because it does not forward that seed to many seed-aware tools

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_grouped_by_file_2026-03-09_run26.md`
- **Affected file:**
  - `tools/targeted_sweep.py`

**Problem:** The sweep-level CLI exposes `--seed` and records that seed in the parent `run.json`, but several child tools are still invoked without `--seed` and therefore fall back to their own default seed (`1337`). A sweep run invoked as `--seed 4242` can therefore produce a top-level bundle stamped with `seed = 4242` while multiple child bundles inside `child_runs/` record `seed = 1337`. The bundle looks like a single-seed run even though it executed as a mixed-seed aggregate.

**Expected:** If the parent sweep exposes `--seed`, every seed-aware child invocation should inherit that explicit seed or the parent artifact should record, surface, and justify per-child seed divergence explicitly.

**Fix:** Thread `--seed` through every seed-aware child tool invocation in `targeted_sweep.py`, and add a validation step that checks the emitted child `run.json` files for seed consistency before the parent report claims a single sweep seed.

## Existing Bug Enrichments Added In v26

### BUG-82 enrichment: the built-in harness simulator still cannot exercise the `flow` learner-state path

Additional evidence folded into `BUG-82` from `session_state_nondeterminism_findings_round45.md`:
- `harness_session.py` still emits only short built-in learner answers (`30-36` characters), which keeps every default turn in `frustrated`
- the underlying session loop can still reach `flow` immediately when given a longer deterministic answer, so the harness fixture remains narrower than the real runtime state space

This is the same learner-state observability and behaviorally dead `flow` branch family already tracked by `BUG-82`.

### BUG-50 enrichment: `seed_sweep.py` still drops mirror privacy-mode execution details from its artifacts

Additional evidence folded into `BUG-50` from `session_state_nondeterminism_findings_round45.md`:
- two `seed_sweep.py` runs that differ only in `DAEDALUS_MIRROR_SEND_USER_CONTENT` still normalize to identical `seed_sweep_report.json` content even though the executed runtime changes `mirror_meta.prompt_mode` between `redacted` and `raw`

This is the same mirror privacy-state propagation and artifact-audibility defect already tracked by `BUG-50`.

### BUG-18 enrichment: graph invariant checking still crashes or passes on more malformed graph shapes

Additional evidence folded into `BUG-18` from `graph_mirror_round20_newbugs21_report.zip` and `new_bugs_round44_bundle.zip`:
- a valid JSON array root still crashes `graph_invariant_checker.py` and can leave an empty run directory instead of a report
- schema-invalid graph fields such as boolean `title`, boolean `summary`, integer `required_keywords` items, and integer `fragility_flags` items still pass through the checker

This remains the same graph-checker malformed-input and schema-validation family already tracked by `BUG-18`.

### BUG-17 enrichment: detector phrase coverage and type-handling remain too narrow

Additional evidence folded into `BUG-17` from `graph_mirror_round20_newbugs21_report.zip`:
- `mirror_leakage_detector.py` still crashes on truthy non-string `mirror.answer` values such as boolean `true`
- the detector still misses additional coaching phrasings such as `A good place to start is to ...`, `Why not ...?`, `It would be a good idea to ...`, `One place to start is to ...`, and `A helpful place to begin is to ...`

This remains the same detector narrowness and malformed-answer handling family already tracked by `BUG-17`.

### BUG-40 enrichment: more tools still accept malformed or impossible `--issue` values and emit bundles with them

Additional evidence folded into `BUG-40` from `xyzgl_bug_findings_20260309_fresh23.zip` and `graph_mirror_round20_newbugs21_report.zip`:
- `curriculum_corpus_linter.py` still accepts impossible calendar dates such as `ISSUE-20260231-001`
- `graph_invariant_checker.py` still accepts junk issue IDs such as `not-an-issue` and writes a `PASS` bundle with the invalid `issue_id`

This is the same malformed-issue acceptance family already tracked by `BUG-40`.

### BUG-106 enrichment: `secret_scanner.py` still misses more raw token families, private-key blocks, connection strings, and credential-bearing URLs

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round73.md`, `xyzgl_bug_findings_20260309_fresh24.zip`, `xyzgl_bug_findings_20260309_fresh23.zip`, and `new_bugs_round44_bundle.zip`:
- raw token literals still pass for `gho_...`, `ghs_...`, and `xapp-1-...`
- private-key material still passes for `BEGIN OPENSSH PRIVATE KEY`, `BEGIN ENCRYPTED PRIVATE KEY`, and `BEGIN PGP PRIVATE KEY BLOCK`
- Azure storage connection strings with `AccountKey=` still pass
- additional credential-bearing URL families still pass, including `couchbase://`, `couchbases://`, `influxdb://`, `stomp://`, `telnet://`, and `rtmp://`
- the raw round-44 bundle also reconfirms that bare secret-shaped `sk-...` content still slips through

This remains the same broad secret false-negative family already tracked by `BUG-106`.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v15.0_20260309_150143.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- `new_bug_session_prompt_meta_unsanitized_leaks_paths_package.zip` also overlaps existing `BUG-95` and `BUG-115` themes, but it is promoted separately here because the core defect is a distinct cross-surface inconsistency: `route_turn()` sanitizes prompt metadata while session-phase exports do not.
- `session_state_nondeterminism_findings_round45.md` otherwise contributed only existing `BUG-82` and `BUG-50` evidence.
- `graph_mirror_round20_newbugs21_report.zip` otherwise contributed only existing graph-checker, malformed-answer, and detector-coverage families (`BUG-18`, `BUG-17`, `BUG-40`).
- `new_bugs_round44_bundle.zip` did not include a prose report body; its raw evidence was reviewed and folded into existing `BUG-18` and `BUG-106` families.
- `xyzgl_bug_findings_20260309_fresh23.zip` contributed one existing malformed-issue case (`BUG-40`) and additional secret-scanner misses (`BUG-106`).
- `xyzgl_bug_findings_20260309_fresh24.zip` contributed only additional secret-scanner false-negative families for `BUG-106`.
- `XYZGL_new_bug_report_round73.md` contributed only additional credential-bearing URL false negatives for `BUG-106`.
- `new_bugs_grouped_by_file_2026-03-09_run26.md` contributed one new defect (`BUG-147`) and no additional independent bug families.

## Recommended Fix Order For The New Bugs

1. `BUG-146`
2. `BUG-147`

## Preserved Prior Master Body (v25 Combined)
# XYZGL Master Bug Report - Final Unified (v25 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v24_20260309_094857.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round42.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round41.md`
- `c:\Users\misha\Downloads\new_bugs_round41_bundle.zip`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-09_run22.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round71.md`
- `c:\Users\misha\Downloads\BUGPACK_v14.7_20260309_134630.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260309_fresh20.zip`
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs19_report.zip`
- `c:\Users\misha\Downloads\round20_pass8_new_bug_bundle.zip`
- `c:\Users\misha\Downloads\new_bug_router_swallows_tutor_fault_backend_package.zip`
- `c:\Users\misha\Downloads\round45_new_replay_protocol_bugs.zip`

This v25 addendum supersedes the v24 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v24 master: 144
- New unique XYZGL defects added in this update: 1
- Existing bug enrichments added in this update: 12 groups
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 145

New defect IDs added here:
- `BUG-145`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `session_state_nondeterminism_findings_round42.md`
- `session_state_nondeterminism_findings_round41.md`
- `new_bugs_round41_bundle.zip`
- `new_bugs_grouped_by_file_2026-03-09_run22.md`
- `XYZGL_new_bug_report_round71.md`
- `xyzgl_bug_findings_20260309_fresh20.zip`
- `graph_mirror_round20_newbugs19_report.zip`
- `round20_pass8_new_bug_bundle.zip`
- `new_bug_router_swallows_tutor_fault_backend_package.zip`
- `round45_new_replay_protocol_bugs.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.7_20260309_134630.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v25

### BUG-145: `ontario_claims_citation_guard.py` rejects explicit `[src:...]` citations unless the cited pair is also present in prompt grounding refs

- **Severity:** Medium-High
- **Phase:** 6
- **Source:** `round20_pass8_new_bug_bundle.zip`
- **Affected file:**
  - `tools/ontario_claims_citation_guard.py`

**Problem:** `_scan_text()` parses explicit `[src:source_id:ordinal]` markers into `all_cites`, but then sets the main citation gate from `valid_cites = [c for c in all_cites if c in grounding_refs]`. Under `--enforce`, a turn that contains an Ontario/code-specific claim plus a syntactically valid explicit citation still records `citation_count: 1`, `has_citations: false`, and `FAIL` whenever the cited pair is not also present in `prompt_meta.grounding.snippets`. The documented contract says grounding snippets and/or explicit citations are acceptable, but the implementation only treats a citation as present when it duplicates the runtime grounding refs.

**Expected:** The guard should distinguish `an explicit citation was provided` from `the citation matched a loaded grounding snippet`. Explicit citations should satisfy the citation arm of the contract even when the prompt carried no grounding snippets, while mismatched or unsupported citation targets can still be reported separately.

**Fix:** Track explicit citation presence independently from grounding-backed citation validity. Use `has_cite = bool(all_cites)` or equivalent for the citation-presence gate, keep `valid_citation_count` and `invalid_citation_count` as diagnostics, and only fail unsupported-claim cases when neither grounding nor any explicit citation is present.

## Existing Bug Enrichments Added In v25

### BUG-50 enrichment: `harness_session.py --enable-mirror` is still a dead session-path axis on the default stub route

Additional evidence folded into `BUG-50` from `session_state_nondeterminism_findings_round41.md`:
- toggling only `--enable-mirror` still changes recorded mirror payloads, but the node sequence, teach/eval path, and final `knowledge_graph.json` remain identical

This is the same mirror-enable propagation and session-path audibility defect already tracked by `BUG-50`.

### BUG-52 enrichment: `seed_sweep.py` top-level artifacts still stamp the controller seed instead of the actual swept seeds

Additional evidence folded into `BUG-52` from `session_state_nondeterminism_findings_round41.md`:
- `run.json.seed` and `seed_sweep_report.json.seed` still remain `1337` while `seed_range = 11..12` and the recorded sample seeds are `[11, 12]`

This is the same run-identity / seed-metadata mismatch already tracked by `BUG-52`.

### BUG-89 enrichment: the shipped default session and sweep probes still collapse distinct welding topics onto the same generic stub behavior

Additional evidence folded into `BUG-89` from `session_state_nondeterminism_findings_round42.md`:
- `harness_session.py` still visits distinct nodes such as `pos_1f_vs_2f` and `smaw_basic_arc` while serializing the same generic teaching block and question
- `seed_sweep.py` still ships a default text (`Explain 2F vs 1F in welding`) that never reaches a topic-specific tutor path and instead measures the generic fallback branch

This is the same default-topic collapse and generic tutoring defect already tracked by `BUG-89`.

### BUG-18 enrichment: graph invariant checking still passes more schema-invalid node shapes and still misclassifies malformed JSON

Additional evidence folded into `BUG-18` from `new_bugs_round41_bundle.zip` and `graph_mirror_round20_newbugs19_report.zip`:
- missing `title`, non-string `title`, integer `node_id`, non-string `required_keywords`, and non-string `fragility_flags` still pass
- malformed `knowledge_graph.json` and malformed nested `session_report.json` still degrade into `FAIL` with `name 'time' is not defined`
- a `nodes[]` array containing no dict entries still passes as an empty graph

This remains the same graph-checker schema-validation and parse-failure misclassification family already tracked by `BUG-18`.

### BUG-71 enrichment: `mirror_leakage_detector.py` still hides malformed witness shapes as benign `no mirror answers present`

Additional evidence folded into `BUG-71` from `graph_mirror_round20_newbugs19_report.zip`:
- a list-valued nested `payload.session_report` inside a witness envelope is still treated as empty input
- a non-object `mirror` block is still dropped and reported as no answers present

This is the same malformed-input masking family already tracked by `BUG-71`.

### BUG-17 enrichment: detector phrase coverage and role-drift detection remain too narrow

Additional evidence folded into `BUG-17` from `graph_mirror_round20_newbugs19_report.zip` and `round45_new_replay_protocol_bugs.zip`:
- mirror leakage still misses `Focus on ...`, `Check whether ...`, `Look for ...`, `Watch for ...`, and `We'll practice ...`
- tutor / protocol drift scanning still misses role-crossing phrasing like `If I am the mirror ...` and `I will answer as the learner here ...`

This remains the same detector narrowness and false-negative family already tracked by `BUG-17`.

### BUG-111 enrichment: strict replay still trusts tampered control metadata that should be part of the recorded turn contract

Additional evidence folded into `BUG-111` from `round45_new_replay_protocol_bugs.zip`:
- changing stored `config.enable_mirror` still yields an equivalent replay outcome
- slash-vs-backslash drift in stored `config.protocol_path` still passes because replay trusts or normalizes the tampered stored value too loosely

This is the same replay-contract omission family already tracked by `BUG-111`.

### BUG-38 enrichment: `prompt_snapshot_guard.py` still self-seeds a missing baseline without `--update`

Additional evidence folded into `BUG-38` from `round20_pass8_new_bug_bundle.zip`:
- deleting `snapshots/prompt_snapshots.json` and running a normal audit still recreates the baseline and returns `PASS`

This is the same baseline self-seeding defect already tracked by `BUG-38`.

### BUG-59 enrichment: `retrieval_eval_bench.py` still allocates an empty run directory before input validation fails

Additional evidence folded into `BUG-59` from `round20_pass8_new_bug_bundle.zip`:
- a missing bench file still produces `INCOMPLETE` only after creating an empty run directory with no `run.json`, report JSON, or summary markdown

This is the same run-dir allocation / input-validation divergence already tracked by `BUG-59`.

### BUG-40 enrichment: more top-level and child tools still accept malformed or impossible `--issue` values

Additional evidence folded into `BUG-40` from `xyzgl_bug_findings_20260309_fresh20.zip` and `round20_pass8_new_bug_bundle.zip`:
- `targeted_sweep.py` still accepts `ISSUE-20260231-001` and writes durable parent artifacts
- `retrieval_eval_bench.py`, `latency_cost_budget_enforcer.py`, and `curriculum_corpus_linter.py` still accept junk issue IDs while `stage_timing_profiler.py` rejects them

This is the same malformed-issue acceptance family already tracked by `BUG-40`.

### BUG-106 enrichment: `secret_scanner.py` still misses more credential-bearing URL families and live secret literal forms

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round71.md` and `xyzgl_bug_findings_20260309_fresh20.zip`:
- credential-bearing `smtps://`, `imaps://`, `pop3s://`, `mqtts://`, `ws://`, `wss://`, `rsync://`, and `cassandra://` URLs still pass
- GitHub fine-grained PATs (`github_pat_...`) and AWS secret access key values still pass

This remains the same broad secret false-negative family already tracked by `BUG-106`.

### BUG-127 enrichment: more tools still overclaim determinism while deriving run identity from wall-clock time and entropy

Additional evidence folded into `BUG-127` from `new_bugs_grouped_by_file_2026-03-09_run22.md`:
- `doc_code_link_checker.py` and `mutation_suite.py` still write `deterministic: true` while their run IDs depend on time plus randomness

This is the same determinism-metadata mismatch family already tracked by `BUG-127`.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v14.7_20260309_134630.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- `new_bug_router_swallows_tutor_fault_backend_package.zip` was reviewed but not promoted as a new top-level defect because it asserts the opposite policy expectation from already-tracked `BUG-01`. The current master already treats non-strict tutor fallback as the intended contract unless `DAEDALUS_REQUIRE_REAL_BACKENDS=1` is set, so promoting the router-fault package separately would make the master internally contradictory. The package is retained as alternative-fix context for `BUG-01` rather than counted as a second open bug.
- `session_state_nondeterminism_findings_round41.md` otherwise contributed only existing `BUG-50` and `BUG-52` evidence.
- `session_state_nondeterminism_findings_round42.md` otherwise contributed only existing `BUG-89` evidence.
- `new_bugs_round41_bundle.zip` contributed only graph-checker schema-validation gaps already tracked by `BUG-18`.
- `new_bugs_grouped_by_file_2026-03-09_run22.md` contributed only determinism-metadata mismatch evidence already tracked by `BUG-127`.
- `XYZGL_new_bug_report_round71.md` contributed only additional secret-scanner false-negative families for `BUG-106`.
- `xyzgl_bug_findings_20260309_fresh20.zip` contributed only additional malformed-issue and secret-scanner evidence for `BUG-40` and `BUG-106`.
- `graph_mirror_round20_newbugs19_report.zip` contributed only existing graph-checker, malformed-input, and detector-coverage bug families (`BUG-18`, `BUG-71`, `BUG-17`).
- `round20_pass8_new_bug_bundle.zip` contributed one new defect (`BUG-145`) and otherwise folded into existing `BUG-38`, `BUG-59`, and `BUG-40`.
- `round45_new_replay_protocol_bugs.zip` contributed only replay-contract and detector-coverage evidence for `BUG-111` and `BUG-17`.

## Recommended Fix Order For The New Bugs

1. `BUG-145`

## Preserved Prior Master Body (v24 Combined)
# XYZGL Master Bug Report - Final Unified (v24 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v23_20260309_091759.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\new_bug_stub_tutor_breaks_teach_probe_question_contract_package.zip`
- `c:\Users\misha\Downloads\round20_pass7_new_bug_bundle.zip`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round70.md`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-09_run20.md`
- `c:\Users\misha\Downloads\new_bugs_round40_bundle.zip`
- `c:\Users\misha\Downloads\BUGPACK_v14.6_20260309_133435.zip`

This v24 addendum supersedes the v23 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v23 master: 140
- New unique XYZGL defects added in this update: 4
- Existing bug enrichments added in this update: 5 groups
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 144

New defect IDs added here:
- `BUG-141`
- `BUG-142`
- `BUG-143`
- `BUG-144`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `new_bug_stub_tutor_breaks_teach_probe_question_contract_package.zip`
- `round20_pass7_new_bug_bundle.zip`
- `XYZGL_new_bug_report_round70.md`
- `new_bugs_grouped_by_file_2026-03-09_run20.md`
- `new_bugs_round40_bundle.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.6_20260309_133435.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v24

### BUG-141: the default stub tutor backend breaks the TEACH/PROBE `Q:` contract and collapses both phases onto the same generic fallback question

- **Severity:** High
- **Phase:** 3
- **Source:** `new_bug_stub_tutor_breaks_teach_probe_question_contract_package.zip`
- **Affected files:**
  - `xyzgl/backends/stub.py`
  - `xyzgl/orchestrator/tutor_phases.py`
  - `xyzgl/orchestrator/parsing.py`

**Problem:** `run_teach_phase()` and `run_probe_phase()` require the tutor backend to emit a `Q:`-prefixed question line so `parse_question()` can preserve the teaching block and the intended follow-up question. The default stub tutor never emits that contract. In the default deterministic/local path, TEACH falls back to the same generic `Q: Can you explain your reasoning step by step?`, and PROBE can also discard the pointed probe question entirely.

**Expected:** The default stub backend should satisfy the same minimal phase contract as the real tutor path, or the phase runners must preserve node/probe question semantics when the backend omits the `Q:` line. Default local runs should not silently collapse TEACH and PROBE into the same generic fallback question.

**Fix:** Teach the stub tutor to emit a deterministic `Q:` line for TEACH/PROBE prompts, and keep phase-level fallback logic so `run_probe_phase()` preserves the caller-supplied pointed question when backend output is generic.

### BUG-142: `reground_cadence_verifier.py` rejects valid standalone `session_report@1` artifacts even though its CLI claims to accept report JSON inputs

- **Severity:** Medium
- **Phase:** 6
- **Source:** `round20_pass7_new_bug_bundle.zip`
- **Affected file:**
  - `tools/reground_cadence_verifier.py`

**Problem:** The verifier succeeds on the repo's witness-wrapped `session_report.json`, but fails on the exact same session payload after extracting the inner top-level `session_report@1` document to a standalone JSON file. Its extractor only looks under `payload.session_report` and never accepts a tool-native top-level session report, so valid normalized artifacts fail with `could not extract prompt_meta`.

**Expected:** A tool that claims to accept a report JSON should accept both supported repo shapes: a witness-wrapped session artifact and a standalone top-level `session_report@1` document.

**Fix:** Accept tool-native top-level `session_report@1` documents first, then fall back to the witness-wrapper extraction path.

### BUG-143: `secret_scanner.py` can false-positive on example/test credentials because placeholder detection ignores surrounding file context

- **Severity:** Medium
- **Phase:** 6
- **Source:** `round20_pass7_new_bug_bundle.zip`
- **Affected file:**
  - `tools/secret_scanner.py`

**Problem:** The scanner's placeholder logic calls `_is_placeholder_match(token, token)`, so it never sees the surrounding file text that says a credential is an example, dummy value, or docs-only placeholder. A line such as `# example credential format for docs only` followed by an example `OPENAI_API_KEY=...` still produces a live-secret hit under enforcement.

**Expected:** Placeholder/example suppression should evaluate the surrounding matched context, not just the token text repeated as its own context, so documentation samples and clearly marked test fixtures are not mislabeled as real secret leaks.

**Fix:** Pass surrounding match/file context into `_is_placeholder_match(...)`, and apply example/dummy/test markers to the full matched snippet rather than the token alone.

### BUG-144: `coverage_gate.py` and `ci_gate.py` create nested `child_runs/` bundles but omit them from `run.json.outputs`

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_grouped_by_file_2026-03-09_run20.md`
- **Affected files:**
  - `tools/coverage_gate.py`
  - `tools/ci_gate.py`

**Problem:** Both parent tools materialize nested `child_runs/` directories containing the smoke/child tool bundles that explain their top-level results, but the parent `run.json.outputs` lists only the top-level reports and metadata. Consumers that trust the declared artifact manifest cannot discover the child bundles even though the parent report depends on them.

**Expected:** When a parent bundle emits nested `child_runs/` artifacts, the directory is declared in `run.json.outputs` so downstream tooling can discover the full run bundle from the manifest alone.

**Fix:** Add `child_runs/` to `run.json.outputs` whenever the parent tool creates child bundles.

## Existing Bug Enrichments Added In v24

### BUG-106 enrichment: `secret_scanner.py` still misses more credential-bearing URL families and bare literal secret forms

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round70.md` and `new_bugs_round40_bundle.zip`:
- `ssh://user:pass@...`
- `git+https://user:pass@...`
- `mqtt://user:pass@...`
- `pop3://user:pass@...`
- `couchdb://user:pass@...`
- `elasticsearch://user:pass@...`
- bare Google API keys (`AIza...`) still pass cleanly in literal-only files

This remains the same broad secret-literal and secret-bearing-URL false-negative family already tracked by `BUG-106`.

### BUG-127 enrichment: more tooling still overclaims determinism while routing run identity through time/entropy-based helpers

Additional evidence folded into `BUG-127` from `new_bugs_grouped_by_file_2026-03-09_run20.md`:
- `prompt_snapshot_guard.py` still records `deterministic: true` while deriving run identity through `tools/run_paths.py::make_run_id()`
- the grouped evidence also confirms the shared helper remains wall-clock/time plus randomness based, so deterministic same-input reruns still produce different run IDs

This is the same determinism-metadata mismatch family already tracked by `BUG-127`.

### BUG-39 enrichment: `backend_contract_probe.py` still falsely fails valid non-raising fault modes beyond `slow`

Additional evidence folded into `BUG-39` from `round20_pass7_new_bug_bundle.zip`:
- `DAEDALUS_FAULT_MODE=empty` still yields `expected backend to raise, but it returned normally`

This is the same non-raising-fault misclassification family already tracked by `BUG-39`.

### BUG-17 enrichment: detector phrase coverage and false-positive handling remain too narrow

Additional evidence folded into `BUG-17` from `round20_pass7_new_bug_bundle.zip` and `new_bugs_round40_bundle.zip`:
- `mirror_leakage_detector.py` still false-fails learner-style uncertainty such as `I don't know yet. Maybe the gap is uneven.` because of the bare `do|don't` pattern
- `mirror_leakage_detector.py` still passes obvious tutor-style phrasing such as `In today's lesson, let's practice ...`

This remains the same detector-correctness and rule-narrowness family already tracked by `BUG-17`.

### BUG-18 enrichment: graph invariant checking still passes schema-invalid node structures and missing required fields

Additional evidence folded into `BUG-18` from `new_bugs_round40_bundle.zip`:
- non-object entries inside `knowledge_graph.nodes` are still silently dropped instead of failed
- `fragility_flags` with the wrong type still pass
- missing required `summary` fields still pass

This is the same graph-checker schema-validation gap already tracked by `BUG-18`.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v14.6_20260309_133435.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- `round20_pass7_new_bug_bundle.zip` finding 2 was folded into existing `BUG-17`, finding 3 into existing `BUG-39`, and finding 4 into new `BUG-143` rather than counted twice.
- `XYZGL_new_bug_report_round70.md` contributed only additional secret-scanner false-negative families and was folded into existing `BUG-106`.
- `new_bugs_round40_bundle.zip` contributed only existing graph-checker and mirror-detector bug families (`BUG-18`, `BUG-17`) plus one more bare-literal secret miss for `BUG-106`.
- `new_bugs_grouped_by_file_2026-03-09_run20.md` contributed one new parent-manifest defect (`BUG-144`) and otherwise folded into existing determinism-metadata bug `BUG-127`.
- The probe-side part of `new_bug_stub_tutor_breaks_teach_probe_question_contract_package.zip` overlaps with the already-tracked `BUG-09` symptom, but the broader default stub phase-contract failure is promoted here as a distinct root-cause bug because it also breaks TEACH-phase questioning on the default local path.

## Recommended Fix Order For The New Bugs

1. `BUG-141`
2. `BUG-142`
3. `BUG-144`
4. `BUG-143`

## Preserved Prior Master Body (v23 Combined)
# XYZGL Master Bug Report - Final Unified (v23 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v22_20260309_090803.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs16_report.zip`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-09_run18.md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260309_fresh16.zip`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round37.md`
- `c:\Users\misha\Downloads\new_bug_invalid_protocol_silently_falls_back_to_builtin_package.zip`
- `c:\Users\misha\Downloads\new_bug_invalid_protocol_silently_falls_back_to_builtin_package (1).zip`
- `c:\Users\misha\Downloads\BUGPACK_v14.3_20260309_130307.zip`

This v23 addendum supersedes the v22 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v22 master: 138
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 7 groups
- Duplicate inputs collapsed: 1 copy
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 140

New defect IDs added here:
- `BUG-139`
- `BUG-140`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `graph_mirror_round20_newbugs16_report.zip`
- `new_bugs_grouped_by_file_2026-03-09_run18.md`
- `xyzgl_bug_findings_20260309_fresh16.zip`
- `session_state_nondeterminism_findings_round37.md`
- `new_bug_invalid_protocol_silently_falls_back_to_builtin_package.zip`

### Duplicate copies collapsed into the same evidence set
- `new_bug_invalid_protocol_silently_falls_back_to_builtin_package (1).zip`
  - duplicate copy of `new_bug_invalid_protocol_silently_falls_back_to_builtin_package.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.3_20260309_130307.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v23

### BUG-139: `graph_invariant_checker.py` and `mirror_leakage_detector.py` misattribute cross-issue witness artifacts because they trust the CLI `--issue` label and never verify embedded artifact issue metadata

- **Severity:** High
- **Phase:** 6
- **Source:** `graph_mirror_round20_newbugs16_report.zip`
- **Affected files:**
  - `tools/graph_invariant_checker.py`
  - `tools/mirror_leakage_detector.py`

**Problem:** Both tools accept witness-backed session evidence whose embedded `issue_id` belongs to one issue while the operator invokes the tool with a different `--issue`. They then emit reports labeled only with the CLI issue and never surface the mismatch. A graph/session pass or a leakage finding can therefore be attributed to issue A even when the source evidence actually came from issue B.

**Expected:** Tooling that consumes witness/session artifacts cross-checks the embedded artifact issue metadata against the CLI `--issue` and fails or downgrades on mismatch, or at minimum records both identities explicitly so the report is not silently misattributed.

**Fix:** Parse and compare embedded `issue_id` metadata from the artifact wrapper/session document against the CLI issue before reporting success/failure, and reject or explicitly flag mismatches.

### BUG-140: `DAEDALUS_ENFORCE_DETERMINISM` is a dead control surface, so harness and sweep workflows can claim determinism-mode coverage while executing the same path

- **Severity:** Medium
- **Phase:** 4
- **Source:** `session_state_nondeterminism_findings_round37.md`
- **Affected files:**
  - `xyzgl/config.py`
  - `tools/harness_session.py`
  - `tools/seed_sweep.py`

**Problem:** The repository exposes `DAEDALUS_ENFORCE_DETERMINISM` in config and docs, but flipping it between `0` and `1` does not change the executed harness or sweep path. The round-37 repro shows identical normalized artifacts, node sequences, tutor questions, and reply hashes across both modes. The same report's code search found the symbol only in config/docs and helper setup, with no live runtime consumer on the exercised path.

**Expected:** If the flag is exposed as a real control axis, changing it must alter the routed execution contract or at least be recorded as an intentional no-op. Otherwise the flag should be removed from the exposed configuration surface so harness/sweep tooling does not imply determinism-mode coverage that does not exist.

**Fix:** Either thread `enforce_determinism` into the actual routed execution path and artifact metadata, or remove/deprecate the flag from the public config/docs until it has a real runtime effect.

## Existing Bug Enrichments Added In v23

### BUG-27 enrichment: invalid protocol fallback still silently replaces configured protocol files with the tiny built-in fallback bundle

Additional evidence folded into `BUG-27` from `new_bug_invalid_protocol_silently_falls_back_to_builtin_package.zip`:
- missing, absolute, outside-repo, non-file, oversized, and unreadable protocol paths still collapse into the built-in fallback protocol instead of surfacing a configuration failure
- prompt construction still cannot distinguish a real protocol load from fallback injection because the prompt path is recorded but fallback use is not

This is the same fail-open protocol downgrade family already tracked by `BUG-27`.

### BUG-127 enrichment: more audit tools still overclaim determinism while deriving run identity from wall-clock time or entropy

Additional evidence folded into `BUG-127` from `new_bugs_grouped_by_file_2026-03-09_run18.md`:
- `graph_invariant_checker.py`
- `reground_cadence_verifier.py`
- `repro_replay_diff.py`
- `mirror_calibration_bench.py`
- `ontario_claims_citation_guard.py`
- `node_evolution_diff.py`

These tools still write `"deterministic": true` while allocating run IDs from wall-clock time and randomness, so same-input reruns do not produce stable run identity.

### BUG-34 enrichment: `property_turn_fuzzer.py` still emits a non-canonical `run.json`

Additional evidence folded into `BUG-34` from `xyzgl_bug_findings_20260309_fresh16.zip`:
- `tools/property_turn_fuzzer.py` still writes `run.json` with direct `json.dumps(...).write_text(...)`, and `artifact_roundtrip.py --strict` still flags the emitted metadata as changed

This is the same non-canonical property-fuzzer artifact defect already tracked by `BUG-34`.

### BUG-81 enrichment: more fresh runs independently reconfirm the existing non-canonical `run.json` family

Additional evidence folded into `BUG-81` from `xyzgl_bug_findings_20260309_fresh16.zip`:
- `tools/atheris_fuzz_router.py`
- `tools/reground_cadence_verifier.py`
- `tools/mirror_calibration_bench.py`

These are the same canonical-artifact contract failures already tracked by `BUG-81`.

### BUG-18 enrichment: graph invariant checking still treats internally inconsistent session provenance as valid evidence

Additional evidence folded into `BUG-18` from `graph_mirror_round20_newbugs16_report.zip`:
- `graph_invariant_checker.py` still accepts `turn_index` values that exceed the embedded `session_report.max_turns`

This is the same graph/session schema-validation and provenance-consistency gap already tracked by `BUG-18`.

### BUG-71 enrichment: `mirror_leakage_detector.py` still processes impossible session metadata instead of rejecting malformed session-shaped input

Additional evidence folded into `BUG-71` from `graph_mirror_round20_newbugs16_report.zip`:
- the detector still reports findings at `turn_index` values that exceed the embedded `max_turns` budget instead of rejecting the session artifact as internally inconsistent

This is the same schema-enforcement defect already tracked by `BUG-71`.

### BUG-17 enrichment: mirror leakage detection still misses more soft advisory phrasings

Additional evidence folded into `BUG-17` from `graph_mirror_round20_newbugs16_report.zip`:
- `mirror_leakage_detector.py` still misses teacher-like advice phrased as `You'd be wise to ...`, `My first move would be ...`, and `It makes sense to ...`

This remains the same detector-narrowness family already tracked by `BUG-17`.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v14.3_20260309_130307.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- `xyzgl_bug_findings_20260309_fresh16.zip` contained only already-tracked non-canonical `run.json` failures (`BUG-34`, `BUG-81`).
- `new_bugs_grouped_by_file_2026-03-09_run18.md` contained only already-tracked determinism-metadata mismatch evidence (`BUG-127`).
- The remaining graph/mirror bundle findings were folded into existing graph consistency (`BUG-18`), malformed-session acceptance (`BUG-71`), and detector phrase-coverage (`BUG-17`) families.

## Recommended Fix Order For The New Bugs

1. `BUG-139`
2. `BUG-140`

## Preserved Prior Master Body (v22 Combined)
# XYZGL Master Bug Report - Final Unified (v22 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v21_20260308_213912.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh14.zip`
- `c:\Users\misha\Downloads\round41_new_replay_protocol_bugs.zip`
- `c:\Users\misha\Downloads\new_bug_invalid_graph_silently_falls_back_to_default_curriculum_package.zip`
- `c:\Users\misha\Downloads\round20_pass4_new_bug_bundle.zip`
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs14_report.zip`
- `c:\Users\misha\Downloads\BUGPACK_v14.1_20260308_231104.zip`

This v22 addendum supersedes the v21 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v21 master: 134
- New unique XYZGL defects added in this update: 4
- Existing bug enrichments added in this update: 5 groups
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 138

New defect IDs added here:
- `BUG-135`
- `BUG-136`
- `BUG-137`
- `BUG-138`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `xyzgl_bug_findings_20260308_fresh14.zip`
- `round41_new_replay_protocol_bugs.zip`
- `new_bug_invalid_graph_silently_falls_back_to_default_curriculum_package.zip`
- `round20_pass4_new_bug_bundle.zip`
- `graph_mirror_round20_newbugs14_report.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.1_20260308_231104.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v22

### BUG-135: `xyzgl.knowledge.graph.load_graph()` silently swaps in the built-in default curriculum when an explicit graph file exists but is invalid

- **Severity:** High
- **Phase:** 1
- **Source:** `new_bug_invalid_graph_silently_falls_back_to_default_curriculum_package.zip`
- **Affected file:**
  - `xyzgl/knowledge/graph.py`

**Problem:** `load_graph()` returns `default_graph()` not only for the missing-file bootstrap case, but also when the operator-supplied graph file already exists and is malformed, oversized, unreadable, or rejected for duplicate keys. That means a broken custom graph silently turns into the built-in Ontario welding demo curriculum instead of surfacing a load failure.

**Expected:** Missing graph files may fall back to the bundled default graph, but invalid existing graph files should fail closed or return an explicit empty/error state with surfaced diagnostics. Runtime should not silently substitute unrelated curriculum content for a broken operator-supplied graph.

**Fix:** Reserve `default_graph()` for the missing-file path only. For invalid existing graph files, raise a structured load error or return an explicit empty graph/error result that the caller must handle.

### BUG-136: `protocol_drift_radar.py` identifies direct JSON artifacts by literal filename instead of artifact schema/content

- **Severity:** Medium
- **Phase:** 6
- **Source:** `round20_pass4_new_bug_bundle.zip`
- **Affected file:**
  - `tools/protocol_drift_radar.py`

**Problem:** In direct-file mode the tool dispatches on `target.name == "session_report.json"` and `target.name == "turn_report.json"`. The same valid JSON bytes therefore pass when the file keeps the canonical name but return `INCOMPLETE: no recognizable artifacts found` after staging or renaming under another filename.

**Expected:** Artifact detection should use the JSON schema/content shape (`witness_event@1`, `session_report@1`, `turn_report@1`) rather than the literal filename, so valid artifacts remain analyzable after renaming or external staging.

**Fix:** Parse the file first, detect the supported artifact kind from `schema_version` and payload shape, and treat the filename only as an optional hint rather than a hard requirement.

### BUG-137: `ci_gate.py` runs `secret_scanner.py` in non-enforcing mode, so known secret hits can still leave the gate green

- **Severity:** High
- **Phase:** 6
- **Source:** `round20_pass4_new_bug_bundle.zip`
- **Affected file:**
  - `tools/ci_gate.py`

**Problem:** The CI gate invokes `python tools/secret_scanner.py --issue <issue>` without `--enforce`. As a result, seeded secret hits still produce `exit_code: 0` in the gate step even though the same input fails immediately when `secret_scanner.py --enforce` is used.

**Expected:** A dedicated CI secret-scanning step fails closed on detected secrets, either by passing `--enforce` to `secret_scanner.py` or by explicitly treating `hit_count > 0` as a gate failure.

**Fix:** Invoke `secret_scanner.py --enforce` from `ci_gate.py` and preserve the failing exit status plus hit-count context in the gate report.

### BUG-138: `mirror_calibration_bench.py` writes `mirror_calibration_summary.md` but never declares it in `run.json.outputs`

- **Severity:** Medium
- **Phase:** 6
- **Source:** `round20_pass4_new_bug_bundle.zip`
- **Affected file:**
  - `tools/mirror_calibration_bench.py`

**Problem:** The bench writes `mirror_calibration_summary.md` on disk in both normal and incomplete paths, but `run.json["outputs"]` lists only `mirror_calibration_report.json` and `run.json`. Downstream tooling that trusts the declared artifact manifest can therefore miss the human-readable summary even though it is part of the run bundle.

**Expected:** Every artifact that the tool produces is declared in `run.json.outputs`, including the Markdown summary.

**Fix:** Add `mirror_calibration_summary.md` to `run.json.outputs` in every exit path before writing the final run metadata.

## Existing Bug Enrichments Added In v22

### BUG-97 enrichment: `backend_contract_probe.py` still downgrades local backend config defects to `INCOMPLETE` under no-network mode

Additional evidence folded into `BUG-97` from `xyzgl_bug_findings_20260308_fresh14.zip`:
- `backend_contract_probe.py --tutor-backends unknown_backend` still exits `2` / `INCOMPLETE` with `config_error: Unknown tutor backend: unknown_backend` even though the failure is purely local and no network path is involved

This is the same backend-classification bug already tracked by `BUG-97`: local config defects are still being hidden as no-network incompletes.

### BUG-81 enrichment: more shipped tools still emit non-canonical `run.json` artifacts that fail strict round-tripping

Additional evidence folded into `BUG-81` from `xyzgl_bug_findings_20260308_fresh14.zip` and `round20_pass4_new_bug_bundle.zip`:
- `mirror_leakage_detector.py` still writes a non-canonical `run.json`
- `redteam_injection_suite.py` still writes a non-canonical `run.json`
- `redteam_rag_poisoning_suite.py` still writes a non-canonical `run.json`
- `mirror_calibration_bench.py` still writes a non-canonical `run.json`

This is the same canonical-artifact contract bug already tracked by `BUG-81`.

### BUG-111 enrichment: `repro_replay_diff.py` still self-validates more tampered turn metadata instead of treating typed contract drift as replay failure

Additional evidence folded into `BUG-111` from `round41_new_replay_protocol_bugs.zip`:
- changing stored `payload.turn_result.config.tutor_backend` from `stub` to `fault` still yields `PASS` and `--strict PASS` because replay trusts the tampered stored config as source-of-truth
- changing `payload.turn_result.prompt_meta.protocol_regrounded` from boolean `true` to integer `1` still yields `PASS` and `--strict PASS` because the comparison path uses loose Python value equality instead of a typed contract check

This is the same replay-contract omission family already tracked by `BUG-111`: strict replay still trusts or loosely compares stored control metadata that should be validated as part of the witness contract.

### BUG-18 enrichment: graph invariant checking still trusts schema-invalid embedded session provenance and ambiguous turn identity

Additional evidence folded into `BUG-18` from `graph_mirror_round20_newbugs14_report.zip`:
- a top-level extra property on the outer `witness_event@1` wrapper still passes graph/session cross-checking
- extra properties on embedded `payload.session_report` and `session_report.turns[]` still pass
- duplicate `turn_index` values pointing to conflicting nodes still pass because the checker reduces provenance to `max(turn_index)` and never validates uniqueness or node consistency

This is the same graph/session schema-validation gap already tracked by `BUG-18`, now independently confirmed on wrapper-level extras and ambiguous turn provenance.

### BUG-17 enrichment: mirror and protocol drift detectors still miss more natural role-takeover phrasing and still false-positive some ordinary learner text

Additional evidence folded into `BUG-17` from `round41_new_replay_protocol_bugs.zip` and `graph_mirror_round20_newbugs14_report.zip`:
- `protocol_drift_radar.py` still passes tutor self-role drift phrased as `As the learner, ...`
- `protocol_drift_radar.py` still misses mirror lesson framing phrased as `In this lesson, ...`
- `mirror_leakage_detector.py` still misses coaching phrased as `Start with ...`, `Double-check ...`, `You are going to want to ...`, `You would be better off ...`, `Take a moment to ...`, and `My advice is to ...`
- `mirror_leakage_detector.py` still false-positives on normal learner phrasing such as `Please give me a second to think about the root gap.`

This remains the same detector-correctness and rule-narrowness family already tracked by `BUG-17`.

## Reviewed But Not Promoted To New Top-Level Defects

- `BUGPACK_v14.1_20260308_231104.zip` was reviewed and excluded as out-of-scope prompt-spec material.
- The fresh14 non-canonical `run.json` findings and the pass4 mirror-tool artifact findings were folded into existing `BUG-81` rather than counted again.
- The round41 replay findings were folded into existing `BUG-111` and `BUG-17` because they extend already-tracked replay-contract and detector-narrowness families.
- The graph/mirror round-20 report's graph checker failures were folded into existing `BUG-18`, and its mirror phrasing misses/false positive were folded into existing `BUG-17`.

## Recommended Fix Order For The New Bugs

1. `BUG-135`
2. `BUG-137`
3. `BUG-136`
4. `BUG-138`

## Preserved Prior Master Body (v21 Combined)
# XYZGL Master Bug Report - Final Unified (v21 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v20_20260308_191341.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run16.md`
- `c:\Users\misha\Downloads\new_bugs_round37_bundle.zip`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round35.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round66.md`
- `c:\Users\misha\Downloads\BUGPACK_v14.1_20260308_231104.zip`

This v21 addendum supersedes the v20 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v20 master: 133
- New unique XYZGL defects added in this update: 1
- Existing bug enrichments added in this update: 4 groups
- Partial / incomplete in-scope bundles reviewed without promotable new defects: 1
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 134

New defect IDs added here:
- `BUG-134`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `new_bugs_grouped_by_file_2026-03-08_run16.md`
- `new_bugs_round37_bundle.zip`
- `session_state_nondeterminism_findings_round35.md`
- `XYZGL_new_bug_report_round66.md`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.1_20260308_231104.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v21

### BUG-134: `artifact_roundtrip.py --fix` cannot rewrite a supported direct JSON file target unless it lives under the repo `runs/` root

- **Severity:** Medium
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round66.md`
- **Affected file:**
  - `tools/artifact_roundtrip.py`

**Problem:** The CLI contract explicitly accepts either `file.json` or `runs/<run_id>/` as the target, but `--fix` hardcodes an allowlist that only permits writes beneath `runs_root()`. A valid direct JSON file target outside `runs/` therefore fails with a write error instead of being canonicalized, even though the non-fix path accepts that target shape.

**Expected:** `--fix` works for both documented target forms, or the CLI contract is narrowed so that direct-file fixing outside `runs/` is explicitly unsupported.

**Fix:** Allow `--fix` for the explicitly supported direct JSON file target path, while retaining containment checks for run-directory rewriting.

## Existing Bug Enrichments Added In v21

### BUG-127 enrichment: more tools still overclaim determinism while using time- or entropy-derived run IDs

Additional evidence folded into `BUG-127` from `new_bugs_grouped_by_file_2026-03-08_run16.md`:
- `retrieval_eval_bench.py`
- `seed_sweep.py`
- `redteam_injection_suite.py`
- `redteam_rag_poisoning_suite.py`

All four tools still write `"deterministic": true` while deriving run IDs from wall-clock time plus randomness, so same-seed reruns do not produce stable run identity.

This is the same determinism-metadata mismatch family already tracked by `BUG-127`.

### BUG-32 enrichment: `harness_session.py` still ignores env-selected `DAEDALUS_MAX_CHARS_IN`

Additional evidence folded into `BUG-32` from `session_state_nondeterminism_findings_round35.md`:
- with `DAEDALUS_MAX_CHARS_IN=1`, the direct env-backed runtime changes the executed teach path materially, but `harness_session.py` still emits the same default-budget session artifact because it continues constructing config from defaults instead of env-backed runtime state

This is the same `XYZGLConfig()` vs `XYZGLConfig.from_env()` harness-state defect already tracked by `BUG-32`, now confirmed to suppress env-selected input-budget state as well.

### BUG-13 enrichment: `seed_sweep.py` still labels raw CLI input instead of the actual env-clamped routed input

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round35.md`:
- under `DAEDALUS_MAX_CHARS_IN=1`, the executed routed input changes from the full text to a one-character clipped input, but the saved sweep report still records the original raw `args.text`
- two materially different routed turns can therefore be labeled as though they executed the same input

This is the same false-proxy / artifact-fidelity family already tracked by `BUG-13`.

### BUG-106 enrichment: `secret_scanner.py` still misses more whole-family provider tokens and secret-bearing URLs

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round66.md`:
- Mapbox `sk.` secret tokens still pass cleanly
- Mailgun `key-...` API keys still pass cleanly
- Brevo / Sendinblue `xkeysib-...` keys still pass cleanly
- Airtable `pat...` tokens still pass cleanly
- Discord webhook URLs still pass cleanly

This remains the same broad secret-literal false-negative family already tracked by `BUG-106`.

## Reviewed But Not Promoted To New Top-Level Defects

- `new_bugs_round37_bundle.zip` contained only four bare stdout snippets:
  - `pd_next_action.stdout`
  - `oc_gaps.stdout`
  - `mirror_turn.stdout`
  - `prompt_extra_case.stdout`
- Those filenames align with already-tracked detector and prompt-snapshot families (`BUG-66`, `BUG-122`, `BUG-17`, `BUG-108`), but the bundle did not include a report body, crafted payloads, or enough contextual evidence to justify a new master defect independently.

## Recommended Fix Order For The New Bugs

1. `BUG-134`

## Preserved Prior Master Body (v20 Combined)

# XYZGL Master Bug Report - Final Unified (v20 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v19_20260308_144552.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round34.md`
- `c:\Users\misha\Downloads\new_bugs_round36_bundle.zip`
- `c:\Users\misha\Downloads\new_bugs_round36_bundle (1).zip`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run15.md`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run15 (1).md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round65.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round65 (1).md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh13.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh13 (1).zip`
- `c:\Users\misha\Downloads\BUGPACK_v14.0_20260308_192916.zip`
- `c:\Users\misha\Downloads\BUGPACK_v14.0_20260308_192916 (1).zip`

This v20 addendum supersedes the v19 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v19 master: 132
- New unique XYZGL defects added in this update: 1
- Existing bug enrichments added in this update: 8 groups
- Duplicate inputs collapsed: 5 copies
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1 bundle family
- Updated open defect total: 133

New defect IDs added here:
- `BUG-133`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `session_state_nondeterminism_findings_round34.md`
- `new_bugs_round36_bundle.zip`
- `new_bugs_grouped_by_file_2026-03-08_run15.md`
- `XYZGL_new_bug_report_round65.md`
- `xyzgl_bug_findings_20260308_fresh13.zip`

### Duplicate copies collapsed into the same evidence set
- `new_bugs_round36_bundle (1).zip`
  - byte-identical to `new_bugs_round36_bundle.zip`
- `new_bugs_grouped_by_file_2026-03-08_run15 (1).md`
  - duplicate copy of `new_bugs_grouped_by_file_2026-03-08_run15.md`
- `XYZGL_new_bug_report_round65 (1).md`
  - duplicate copy of `XYZGL_new_bug_report_round65.md`
- `xyzgl_bug_findings_20260308_fresh13 (1).zip`
  - byte-identical to `xyzgl_bug_findings_20260308_fresh13.zip`
- `BUGPACK_v14.0_20260308_192916 (1).zip`
  - byte-identical to `BUGPACK_v14.0_20260308_192916.zip`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v14.0_20260308_192916.zip`

Reason for exclusion:
- this is another CompanionWriter / Apex prompt-spec bundle, not a defect report about the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v20

### BUG-133: `repro_replay_diff.py` rejects standalone `session_report@1` and `turn_report@1` artifacts in canonical run directories because it hardcodes the witness-event wrapper

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_round36_bundle.zip`
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** When given a normal run directory containing `session_report.json` or `turn_report.json`, the replay tool assumes those files must be witness-wrapped and only attempts to extract `payload.session_report` or `payload.turn_result`. Schema-valid standalone `session_report@1` and `turn_report@1` documents in the canonical filenames are therefore rejected with `cannot extract payload.session_report` or `cannot extract payload.turn_result` even though the artifacts themselves are semantically complete.

**Expected:** `repro_replay_diff.py` accepts the repo's canonical report artifacts whether they are stored as standalone tool-native documents or wrapped inside witness envelopes, and only fails when neither supported form can be extracted.

**Fix:** Teach the loader to accept tool-native `session_report@1` / `turn_report@1` top-level documents first, then fall back to the witness-event wrapper path, with regression coverage for both representations in directory mode.

## Existing Bug Enrichments Added In v20

### BUG-32 enrichment: `harness_session.py` still bypasses env-selected strict real-backend requirements

Additional evidence folded into `BUG-32` from `session_state_nondeterminism_findings_round34.md`:
- under a configuration that should require real backends, `harness_session.py` can still run against stub backends and report a passing result because it continues constructing config state from defaults instead of honoring the strict env-backed runtime contract

This is the same `XYZGLConfig()` vs `XYZGLConfig.from_env()` harness-state defect already tracked by `BUG-32`, now confirmed to suppress strict real-backend requirements as well as other env-selected runtime state.

### BUG-13 enrichment: `seed_sweep.py` still bypasses env-selected strict real-backend requirements and can certify the wrong execution path

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round34.md`:
- with the repo configured to require real backends, `seed_sweep.py` can still execute on the stub route and finish as though the run were a valid strict/backend-authoritative sweep

This is the same false-proxy seed-sweep family already tracked by `BUG-13`: the tool still can certify a non-authoritative execution path as if it were the real one.

### BUG-127 enrichment: `mirror_leakage_detector.py` and `protocol_drift_radar.py` still overclaim determinism while using entropy-based run IDs

Additional evidence folded into `BUG-127` from `new_bugs_grouped_by_file_2026-03-08_run15.md`:
- both tools still write `"deterministic": true` in `run.json`
- both tools still allocate run IDs via `make_run_id()`, which depends on wall-clock time plus entropy instead of a seed-derived identifier
- same-seed reruns therefore still produce different run IDs while claiming deterministic output

This is the same determinism-metadata mismatch family already tracked by `BUG-127`, now confirmed to extend to the mirror-leakage and protocol-drift scanners.

### BUG-66 enrichment: `protocol_drift_radar.py` still ignores `turn_report.payload.turn_result.gaps`

Additional evidence folded into `BUG-66` from `new_bugs_round36_bundle.zip`:
- explicit mirror-to-tutor role drift stored in the schema-valid `turn_result.gaps` field still yields `PASS` with zero findings because the turn-artifact collector only scans `reply` and optional `mirror_prediction`

This is the same turn/session field-coverage defect already tracked by `BUG-66`.

### BUG-122 enrichment: `ontario_claims_citation_guard.py` still ignores unsupported Ontario/code claims in `turn_report.payload.turn_result.next_action`

Additional evidence folded into `BUG-122` from `new_bugs_round36_bundle.zip`:
- unsupported Ontario/code-specific claims placed in the schema-valid `turn_result.next_action` field still pass even under `--enforce`

This is the same citation-guard field-coverage defect already tracked by `BUG-122`.

### BUG-40 enrichment: more issue-scoped tools still accept malformed `--issue` values and emit self-invalid bundles

Additional evidence folded into `BUG-40` from `new_bugs_round36_bundle.zip`:
- `graph_invariant_checker.py`
- `grounding_injection_audit.py`
- `curriculum_corpus_linter.py`
- `property_turn_fuzzer.py`

All four tools still serialize malformed `issue_id` values into their own artifacts and then fail the repo's schema validator on the emitted `run.json`.

This is the same malformed-issue acceptance family already tracked by `BUG-40`.

### BUG-106 enrichment: `secret_scanner.py` still misses more literal-family secrets and connection-string exposures

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round65.md` and `xyzgl_bug_findings_20260308_fresh13.zip`:
- PuTTY private key headers still pass cleanly
- Stripe `sk_test_...` and `rk_test_...` tokens still pass cleanly
- MySQL, Redis, and MongoDB URLs with embedded passwords still pass cleanly
- the fresh13 evidence independently reconfirms misses on raw AWS literals, project-key-style literals, and OpenSSH-style key material

This remains the same broad secret-literal false-negative family already tracked by `BUG-106`.


## Recommended Fix Order For The New Bugs

1. `BUG-133`

## Preserved Prior Master Body (v19 Combined)

# XYZGL Master Bug Report - Final Unified (v19 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v18_20260308_140954.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round59.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round60.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round61.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round28.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round29.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round30.md`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run9.md`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run10.md`
- `c:\Users\misha\Downloads\round20_bug_hunt_bundle.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh7.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh8.zip`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh9.zip`
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs9_report.zip`
- `c:\Users\misha\Downloads\graph_mirror_round20_newbugs10_report.zip`
- `c:\Users\misha\Downloads\new_bugs_round31_bundle.zip`
- `c:\Users\misha\Downloads\new_bugs_round32_bundle.zip`
- `c:\Users\misha\Downloads\round37_new_replay_protocol_bugs.zip`
- `c:\Users\misha\Downloads\new_bug_cli_interactive_ignores_turn_index_package.zip`
- `c:\Users\misha\Downloads\new_bug_session_report_silently_drops_late_turns_package.zip`
- `c:\Users\misha\Downloads\BUGPACK_v13.3_20260308_180937.zip`
- `c:\Users\misha\Downloads\BUGPACK_v13.4_20260308_182107.zip`

This v19 addendum supersedes the v18 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v18 master: 125
- New unique XYZGL defects added in this update: 7
- Existing bug enrichments added in this update: 17 groups
- Overlapping inputs collapsed into the same evidence set: 1 pair
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 2
- Updated open defect total: 132

New defect IDs added here:
- `BUG-126`
- `BUG-127`
- `BUG-128`
- `BUG-129`
- `BUG-130`
- `BUG-131`
- `BUG-132`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `XYZGL_new_bug_report_round59.md`
- `XYZGL_new_bug_report_round60.md`
- `XYZGL_new_bug_report_round61.md`
- `session_state_nondeterminism_findings_round28.md`
- `session_state_nondeterminism_findings_round29.md`
- `session_state_nondeterminism_findings_round30.md`
- `new_bugs_grouped_by_file_2026-03-08_run9.md`
- `new_bugs_grouped_by_file_2026-03-08_run10.md`
- `round20_bug_hunt_bundle.zip`
- `xyzgl_bug_findings_20260308_fresh7.zip`
- `xyzgl_bug_findings_20260308_fresh8.zip`
- `xyzgl_bug_findings_20260308_fresh9.zip`
- `graph_mirror_round20_newbugs9_report.zip`
- `graph_mirror_round20_newbugs10_report.zip`
- `new_bugs_round31_bundle.zip`
- `new_bugs_round32_bundle.zip`
- `round37_new_replay_protocol_bugs.zip`
- `new_bug_cli_interactive_ignores_turn_index_package.zip`
- `new_bug_session_report_silently_drops_late_turns_package.zip`

### Overlapping evidence collapsed into one finding set
- `xyzgl_bug_findings_20260308_fresh8.zip`
- `xyzgl_bug_findings_20260308_fresh9.zip`
  - both bundles repeated the same four findings around repro-smoke artifact impersonation, prompt snapshot coverage, and stage-timing determinism metadata

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v13.3_20260308_180937.zip`
- `BUGPACK_v13.4_20260308_182107.zip`

Reason for exclusion:
- both bundles are CompanionWriter / Apex prompt-spec packages rather than reports about defects in the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v19

### BUG-126: `prompt_snapshot_guard.py` does not actually snapshot a no-protocol prompt for its canonical `no_protocol_no_grounding` case

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_bug_findings_20260308_fresh8.zip`, `xyzgl_bug_findings_20260308_fresh9.zip`
- **Affected files:**
  - `tools/prompt_snapshot_guard.py`
  - `xyzgl/protocols.py`

**Problem:** The canonical snapshot case named `no_protocol_no_grounding` is built with `protocol_reground_every = 0` but also with `turn_index = 0`. `should_reground()` still forces protocol injection on turn 0, so the recorded baseline case sets `protocol_regrounded = true` and never exercises the no-protocol prompt shape that its name claims to protect.

**Expected:** Canonical snapshot cases match the prompt state they claim to cover. A case named `no_protocol_no_grounding` should actually capture a prompt with neither protocol nor grounding present, or the case should be renamed to reflect the real turn-0 semantics.

**Fix:** Build the no-protocol case on a non-zero turn index or add an explicit protocol-disable path for this guard, then assert that the saved case metadata matches the intended case meaning.

---

### BUG-127: Several tools hard-code `run.json.deterministic` in ways that do not match their real run identity or replay semantics

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_grouped_by_file_2026-03-08_run9.md`, `new_bugs_grouped_by_file_2026-03-08_run10.md`, `xyzgl_bug_findings_20260308_fresh8.zip`, `xyzgl_bug_findings_20260308_fresh9.zip`
- **Affected files:**
  - `tools/targeted_sweep.py`
  - `tools/harness_session.py`
  - `tools/coverage_gate.py`
  - `tools/atheris_fuzz_router.py`
  - `tools/stage_timing_profiler.py`

**Problem:** Several tools claim `"deterministic": true` while still allocating run directories from wall-clock time plus entropy, and `stage_timing_profiler.py` goes the opposite direction by hard-coding `"deterministic": false` even though its shipped cases are fixed-seed stub-only runs. The metadata no longer describes actual replayability or artifact stability.

**Expected:** Determinism metadata is derived from the real execution contract. If a tool claims deterministic output, either the emitted artifact identity must also be stable for equivalent deterministic runs, or the tool must clearly separate logical determinism from unique run-directory allocation. Conversely, stub-only fixed-seed runs should not be labeled non-deterministic without a concrete reason.

**Fix:** Derive determinism from actual workload semantics, separate unique run-dir naming from logical reproducibility, and make the deterministic flag consistent across all tool emitters.

---

### BUG-128: Interactive CLI mode ignores `--turn-index`, so resumed sessions silently restart at turn 0

- **Severity:** Medium-High
- **Phase:** 4
- **Source:** `new_bug_cli_interactive_ignores_turn_index_package.zip`
- **Affected files:**
  - `xyzgl/cli.py`
  - `xyzgl/session.py`

**Problem:** The CLI exposes `--turn-index` and honors it in one-shot mode, but interactive mode always calls `SessionState.new()` and starts with `turn_index = 0`. A resumed interactive session therefore shifts protocol reground cadence and prompt metadata even though the operator explicitly requested a different starting turn.

**Expected:** `--turn-index` applies consistently across one-shot and interactive modes, or interactive mode rejects the flag explicitly instead of silently ignoring it.

**Fix:** Initialize interactive `SessionState` from the validated CLI turn index and fail fast on nonsensical negative values.

---

### BUG-129: `run_session()` can execute up to 256 turns while `SessionReport.turns` silently stops recording after 128

- **Severity:** High
- **Phase:** 4
- **Source:** `new_bug_session_report_silently_drops_late_turns_package.zip`
- **Affected file:**
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** The session loop caps execution at `MAX_SESSION_TURNS = 256`, but in-memory reporting is capped separately at `MAX_SESSION_EXPORT_TURNS = 128`. Long sessions therefore continue mutating state and closing nodes after turn 127 while the exported `SessionReport.turns` list silently stops growing, with no truncation flag or dropped-turn count.

**Expected:** Session reports either preserve the full executed turn history or explicitly record truncation metadata such as total executed turns and turns omitted.

**Fix:** Keep all executed turns in memory, or emit explicit truncation metadata and preserve enough late-turn evidence to make the report faithful to the actual session outcome.

---

### BUG-130: `node_evolution_diff.py` ignores the canonical `turns[*].eval.next_action` field when linking close turns

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_round31_bundle.zip`
- **Affected file:**
  - `tools/node_evolution_diff.py`

**Problem:** Close-turn linking checks only a duplicated top-level `next_action` field on session turns. The schema-canonical close decision is stored under `turns[*].eval.next_action`, so real close events are missed unless callers redundantly copy the value into a noncanonical top-level field.

**Expected:** Close-turn linking follows the schema-canonical session turn path and treats any legacy top-level duplication only as a fallback.

**Fix:** Read `eval.next_action` first, preserve compatibility with any legacy top-level field only as fallback, and add regression coverage for both layouts.

---

### BUG-131: `mirror_calibration_bench.py` is effectively inert in shipped CI/sweep wiring because the default threshold is `0.0`

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_bug_findings_20260308_fresh7.zip`
- **Affected files:**
  - `tools/mirror_calibration_bench.py`
  - `tools/ci_gate.py`
  - `tools/targeted_sweep.py`

**Problem:** The bench reports `PASS` with materially weak similarity (`avg_seqmatch` around `0.2765`) because the shipped default threshold is `--min-avg 0.0`, and both `ci_gate.py` and `targeted_sweep.py` invoke the bench without overriding it. In practice the mirror calibration gate cannot fail under normal wiring unless similarity drops below zero.

**Expected:** Shipped CI and sweep wiring enforce a meaningful minimum similarity threshold or require the caller to provide one explicitly.

**Fix:** Raise the default threshold to a nontrivial value, or require explicit threshold configuration from the calling workflow and record the effective threshold in the emitted report.

---

### BUG-132: `retrieval_eval_bench.py` ships with a vacuous benchmark/corpus pair that can pass without proving retrieval quality

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_bug_findings_20260308_fresh7.zip`
- **Affected files:**
  - `tools/retrieval_eval_bench.py`
  - shipped retrieval benchmark / curriculum assets

**Problem:** The shipped benchmark contains three cases and every case expects the same source id, while the shipped curriculum manifest contains only that same single source. A trivial retriever that always returns the lone source therefore passes 3/3 without demonstrating ranking quality, source discrimination, or resistance to source confusion.

**Expected:** The shipped retrieval benchmark includes multiple source ids and at least some cases that can fail when ranking, source selection, or disambiguation is wrong.

**Fix:** Expand the bundled curriculum and benchmark to cover multiple sources with conflicting lexical overlap, then fail fast when the shipped benchmark collapses to a single expected source across all cases.

## Existing Bug Enrichments Added In v19

### BUG-120 enrichment: `validate_schemas.py` still ignores declared nested child JSON under `run.json.outputs`

Additional evidence folded into `BUG-120` from `XYZGL_new_bug_report_round60.md`:
- declared nested child JSON can still be malformed and pass untouched
- declared nested child reports can still be schema-invalid and pass untouched
- unknown declared nested JSON outputs are still ignored completely
- nested child reports can disagree with the parent on `run_id` / `issue_id` without validation ever noticing

This is the same run-bundle completeness and declared-output enforcement defect already tracked by `BUG-120`, now confirmed to extend from missing child artifacts to malformed, invalid, unknown, and identity-mismatched declared nested JSON.

### BUG-79 enrichment: `artifact_roundtrip.py` still ignores declared nested child JSON in directory mode, including `--strict` and `--fix`

Additional evidence folded into `BUG-79` from `XYZGL_new_bug_report_round61.md`:
- malformed nested child JSON still passes in directory mode
- non-canonical nested child JSON is still ignored under `--strict`
- `--fix` still leaves declared nested child JSON untouched
- unknown declared nested child JSON is still skipped entirely

This is the same nested child-run omission defect already tracked by `BUG-79`, now confirmed across malformed, non-canonical, unknown, and fix-mode cases.

### BUG-32 enrichment: `harness_session.py` still discards env-selected protocol path and protocol reground cadence

Additional evidence folded into `BUG-32` from `session_state_nondeterminism_findings_round28.md` and `session_state_nondeterminism_findings_round30.md`:
- the harness still ignores `DAEDALUS_PROTOCOL_PATH` and records the default `STABLE/ROLE_PROTOCOL.md`
- the harness still ignores `DAEDALUS_PROTOCOL_REGROUND_EVERY` unless the CLI flag restates it, so later turns replay the wrong protocol state

This is the same `XYZGLConfig()` vs `XYZGLConfig.from_env()` replay mismatch already tracked by `BUG-32`, now confirmed for both protocol asset selection and protocol-reground cadence.

### BUG-50 enrichment: `harness_session.py` still ignores env-enabled mirror state unless the CLI flag restates it

Additional evidence folded into `BUG-50` from `session_state_nondeterminism_findings_round29.md`:
- with `DAEDALUS_ENABLE_MIRROR=1`, the real routed path still produces mirror output while the harness records `mirror.answer = null` and `mirror.meta = null`
- the same harness only emits mirror artifacts when `--enable-mirror` is passed locally

This is the same env-state elision family already tracked in the master: session replay still silently drops mirror-enabled runtime state unless the operator restates it on the CLI.

### BUG-13 enrichment: `seed_sweep.py` still collapses or mislabels real state axes that matter for reproducibility analysis

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round28.md`, `session_state_nondeterminism_findings_round29.md`, and `session_state_nondeterminism_findings_round30.md`:
- impossible negative `--turn-index` values still alias to turn-0 prompt behavior while the report records the impossible negative state as if it were real
- mirror-on and mirror-off runs can still collapse to indistinguishable sweep artifacts because mirror state is discarded from the report
- raw transport text differences such as CRLF vs LF are still recorded instead of the normalized executed input, even when the routed turn was identical

This remains the same false-proxy / artifact-fidelity family already tracked by `BUG-13`.

### BUG-114 enrichment: `coverage_gate.py` still contaminates its own stdout with child-tool status lines

Additional evidence folded into `BUG-114` from `new_bugs_grouped_by_file_2026-03-08_run9.md`:
- inline child smoke tools still print their own `PASS` / `FAIL: wrote outputs to ...` lines directly to parent stdout before `coverage_gate.py` prints its final status
- the parent tool's stdout is therefore no longer a single unambiguous machine-readable result stream

This is the same reporting-classification family already tracked by `BUG-114`: `coverage_gate.py` still emits misleading top-level outcome text and now also mixes child-tool status lines into the parent status channel.

### BUG-18 enrichment: graph invariant checking still treats embedded session artifacts as unvalidated loose input instead of schema-bound provenance

Additional evidence folded into `BUG-18` from `xyzgl_bug_findings_20260308_fresh7.zip`, `graph_mirror_round20_newbugs9_report.zip`, and `graph_mirror_round20_newbugs10_report.zip`:
- malformed `knowledge_graph.json` still crashes down the retry path because `time` is missing and parse failures still do not cleanly surface as `INCOMPLETE`
- embedded `session_report` objects and embedded `turns[]` entries can still carry forbidden extra properties without failure
- negative `turn_index` values and turns missing all required fields except `turn_index` still pass graph/session cross-checking

This is the same graph/session schema-validation gap already tracked by `BUG-18`, now confirmed across more embedded session-report and turn-object failure modes.

### BUG-17 enrichment: mirror/protocol drift detection still misses more natural advisory phrasing and contracted role claims, and still misclassifies some learner phrasing

Additional evidence folded into `BUG-17` from `graph_mirror_round20_newbugs9_report.zip`, `graph_mirror_round20_newbugs10_report.zip`, and `round37_new_replay_protocol_bugs.zip`:
- `mirror_leakage_detector.py` still misses advisory phrasing such as `It helps to ...`, `Watch for ...`, `If I were you, I would ...`, `Focus on ...`, `You may want to ...`, `A good next step is to ...`, and `Better to ...`
- `protocol_drift_radar.py` still misses natural contracted forms such as `I'm simulating the learner ...` and `I'm the mirror ...`
- explicit tutor-role drift phrased as `teacher` still passes when the existing rules only watch for `tutor`
- ordinary learner uncertainty such as `I don't know if my travel angle is too steep.` can still false-positive because the fallback regex treats bare `do` / `don't` as leakage markers

This remains the same detector-correctness and rule-narrowness family already tracked by `BUG-17`.

### BUG-71 enrichment: `mirror_leakage_detector.py` still normalizes malformed session metadata instead of rejecting it

Additional evidence folded into `BUG-71` from `graph_mirror_round20_newbugs10_report.zip`:
- a string `turn_index` such as `"oops"` is still silently coerced to `0` in findings instead of being rejected as malformed session input

This is the same schema-enforcement defect already tracked by `BUG-71`: the detector still processes malformed session-shaped JSON instead of requiring a valid session artifact before producing findings.

### BUG-66 enrichment: `protocol_drift_radar.py` still misses more turn/session tutor-text fields

Additional evidence folded into `BUG-66` from `new_bugs_round31_bundle.zip` and `new_bugs_round32_bundle.zip`:
- turn artifacts still bypass scanning when role-drift text is stored in `turn_result.next_question`, `turn_result.evaluation`, or `turn_result.teaching_block`
- session artifacts still bypass scanning when role-drift text is stored in `eval.next_question`

This is the same field-coverage defect already tracked by `BUG-66`, now confirmed on additional canonical turn-report and session-report fields.

### BUG-122 enrichment: `ontario_claims_citation_guard.py` still ignores more tutor-authored claim surfaces in both turn and session artifacts

Additional evidence folded into `BUG-122` from `new_bugs_round31_bundle.zip` and `new_bugs_round32_bundle.zip`:
- turn artifacts still bypass enforcement when unsupported Ontario/code claims are stored in `turn_result.evaluation` or `turn_result.next_question`
- session artifacts still bypass enforcement when unsupported Ontario/code claims are stored in `teach.question` or `eval.next_question`

This is the same citation-guard field-coverage defect already tracked by `BUG-122`.

### BUG-106 enrichment: `secret_scanner.py` still misses more literal-family secrets and can suppress otherwise matching tokens because of placeholder-word heuristics

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round59.md` and `new_bugs_round31_bundle.zip`:
- literal-family false negatives still reproduce for `npm_...`, `rk_live_...`, `glrt-...`, `xapp-...`, Mailchimp `32hex-usN`, `sq0atp-...`, and Google OAuth `ya29...`
- an otherwise matching secret-shaped token can still be suppressed when `_is_placeholder_match()` sees placeholder substrings such as `example` inside the token text

This remains the same broad secret-literal false-negative family already tracked by `BUG-106`.

### BUG-111 enrichment: `repro_replay_diff.py` still self-validates tampered stored input beyond the effective clamp window

Additional evidence folded into `BUG-111` from `round37_new_replay_protocol_bugs.zip`:
- appending extra text past the effective `max_chars_in` clamp boundary to stored `payload.turn_result.input` still yields `PASS` and `--strict PASS`
- replay still trusts stored control/input metadata instead of validating the full recorded contract surface

This is the same replay-contract omission family already tracked by `BUG-111`.

### BUG-117 enrichment: `repro_replay_diff.py` still false-fails on inert session mirror telemetry that does not affect replayed behavior

Additional evidence folded into `BUG-117` from `round37_new_replay_protocol_bugs.zip`:
- changing only `session_report.turns[0].mirror.meta.latency_ms` still forces both non-strict and strict replay to `FAIL`
- the replayed session path does not use that telemetry to regenerate behavior, but the comparer still hashes the entire turns array as though all telemetry were behaviorally material

This is the same forward-compatible / inert-metadata false-fail family already tracked by `BUG-117`.

### BUG-113 enrichment: repro smoke artifact impersonation remains reproducible in independent fresh bundles

Additional evidence folded into `BUG-113` from `xyzgl_bug_findings_20260308_fresh8.zip` and `xyzgl_bug_findings_20260308_fresh9.zip`:
- `repro_grounding_protocol_smoke.py` still emits `ci_gate_report.json` with `schema_version = ci_gate_report@1`
- `repro_backends_smoke.py` still emits `backend_fault_report.json` with `schema_version = backend_fault_report@1`

This is the same report-type impersonation defect already tracked by `BUG-113`.

### BUG-01 enrichment: non-strict tutor backend fallback is still independently broken in the round-20 bug-hunt bundle

Additional evidence folded into `BUG-01` from `round20_bug_hunt_bundle.zip`:
- `backend_fault_injector.py` and `repro_backends_smoke.py` still reproduce the same `strict_tutor = require_real_backends() or _is_real_tutor_backend(cfg.tutor_backend)` failure mode
- missing Gemini credentials and unknown tutor backend names still raise instead of degrading to the deterministic stub in non-strict mode

This is the same non-strict tutor fallback defect already tracked by `BUG-01`.

### BUG-22 enrichment: builtin mutation anchors are still stale relative to the current router implementation

Additional evidence folded into `BUG-22` from `round20_bug_hunt_bundle.zip`:
- builtin `MUT-001` and `MUT-002` still fail with `mutation pattern not found`
- the bundle confirms the stale find/replace anchors are still disconnected from the current router implementation

This is the same stale mutation-suite / weak quality-gate problem already tracked by `BUG-22`.

### BUG-53 enrichment: the missing `signal_fidelity_port` companion docs are independently reconfirmed

Additional evidence folded into `BUG-53` from `round20_bug_hunt_bundle.zip`:
- `doc_code_link_checker.py --enforce` still reports missing docs for `signal_fidelity_port`

This is the same missing tool-doc governance defect already tracked by `BUG-53`.

## Reviewed But Not Promoted To New Top-Level Defects

- `round20_bug_hunt_bundle.zip` also notes that `doctor.py` rejects the common `--issue` flag. I did not promote that to a new master bug because `doctor.py` is not a standard issue-scoped artifact emitter, and the more substantive runtime/reporting defects from the same input were already captured elsewhere.
- The two `BUGPACK_v13.x` archives were reviewed and excluded as out-of-scope CompanionWriter / Apex prompt-spec bundles.

## Recommended Fix Order For The New Bugs

1. `BUG-129`
2. `BUG-128`
3. `BUG-127`
4. `BUG-130`
5. `BUG-131`
6. `BUG-132`
7. `BUG-126`

## Preserved Prior Master Body (v18 Combined)# XYZGL Master Bug Report - Final Unified (v18 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v17_20260308_105438.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round58.md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh6.zip`
- `c:\Users\misha\Downloads\round36_new_replay_protocol_bugs (1).zip`
- `c:\Users\misha\Downloads\round36_new_replay_protocol_bugs (2).zip`
- `c:\Users\misha\Downloads\BUGPACK_v13.1_20260308_072900.zip`

This v18 addendum supersedes the v17 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v17 master: 123
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 6 groups
- Duplicate bundles collapsed: 1
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 1
- Updated open defect total: 125

New defect IDs added here:
- `BUG-124`
- `BUG-125`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `XYZGL_new_bug_report_round58.md`
- `xyzgl_bug_findings_20260308_fresh6.zip`
- `round36_new_replay_protocol_bugs (1).zip`

### Duplicate bundle collapsed into the same evidence set
- `round36_new_replay_protocol_bugs (2).zip`
  - byte-identical to `(1)`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `BUGPACK_v13.1_20260308_072900.zip`

Reason for exclusion:
- this bundle is another CompanionWriter/Apex prompt-spec package, not a report about defects in the live XYZGL runtime, harness, replay, or audit toolchain

## New Defects Added In v18

### BUG-124: `property_turn_fuzzer.py` violates its own `--max-len` contract in builtin mode by treating the limit as token count rather than character count

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_bug_findings_20260308_fresh6.zip`
- **Affected file:**
  - `tools/property_turn_fuzzer.py`

**Problem:** `_gen_case()` samples `n = randint(0, max_len)` elements from an alphabet that includes multi-character markers such as `<<<USER>>>` and `<<<END_USER>>>`, then joins them into one string. That means `--max-len 120` does not cap generated case length at 120 characters: the resulting strings can still be substantially longer. The supplied run recorded lengths such as `153`, `162`, `245`, and `247` while reporting a normal `PASS` run under `--max-len 120`.

**Expected:** `--max-len` enforces an actual maximum generated input length in characters, or the option is renamed/documented explicitly as a token-count budget instead of a character cap.

**Fix:** Generate cases against a character budget, trim or reject over-budget results before execution, and ensure the report records the effective length constraint that was actually enforced.

---

### BUG-125: `atheris_fuzz_router.py` reports `PASS` even when Atheris never ran and the tool silently downgraded to the fallback loop

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_bug_findings_20260308_fresh6.zip`
- **Affected file:**
  - `tools/atheris_fuzz_router.py`

**Problem:** If importing `atheris` fails, the tool catches the exception, switches to a small deterministic fallback loop, and still writes `status = "PASS"` with `engine = "fallback"` and a note such as `atheris missing (ModuleNotFoundError)`. The result is a green artifact even though the named coverage-guided engine was unavailable and never executed.

**Expected:** Missing Atheris is reported as `INCOMPLETE` or another downgraded status that clearly distinguishes `real Atheris fuzzing ran` from `fallback loop executed instead`.

**Fix:** Treat missing `atheris` as a non-pass outcome, or emit a separate downgraded status that CI and humans can distinguish from real coverage-guided fuzz success.

## Existing Bug Enrichments Added In v18

### BUG-76 enrichment: `ci_gate.py` still loses a successful session run directory and skips run-dir checks because it sanitizes before extracting

Additional evidence folded into `BUG-76` from `xyzgl_bug_findings_20260308_fresh6.zip`:
- `harness_session` still exits `0`, but `ci_gate_report.json` records `session_run_dir = INCOMPLETE: could not locate session run dir`
- the underlying source still sanitizes absolute paths to `<path>` before `_extract_run_dir()` attempts to recover the child bundle directory

This is the same sanitize-then-parse session-dir loss already tracked by `BUG-76`.

### BUG-119 enrichment: `targeted_sweep.py` still hides the real child failure reason behind generic top-level tail text

Additional evidence folded into `BUG-119` from `xyzgl_bug_findings_20260308_fresh6.zip`:
- the top-level sweep report still collapses failing child-tool output to generic text like `FAIL: wrote outputs to <path>`
- the concrete failure reasons remain visible only inside child-run artifacts, so the grouped-by-file sweep report is still not self-sufficient for bug triage

This is the same lossy child-diagnostics defect already tracked by `BUG-119`.

### BUG-111 enrichment: `repro_replay_diff.py` still self-validates more tampered turn-input contract fields because replay trusts stored execution inputs as source of truth

Additional evidence folded into `BUG-111` from `round36_new_replay_protocol_bugs (1).zip`:
- changing `payload.turn_result.seed` from `1337` to `9999` in a turn bundle still self-validates on the stub path
- changing `payload.turn_result.config.grounding_dir` to a different path while grounding is off also self-validates for the same reason

This is the same replay-contract omission family already tracked by `BUG-111`: strict replay still trusts stored turn/session control metadata instead of independently validating all contract fields that should remain stable.

### BUG-17 enrichment: `protocol_drift_radar.py` still ignores explicit role-leak text hidden in nested `eval.prompt_meta` and turn-level `mirror_meta` fields

Additional evidence folded into `BUG-17` from `round36_new_replay_protocol_bugs (1).zip`:
- explicit text like `I am simulating the learner in this answer.` hidden under `session_report.turns[*].eval.prompt_meta.note` still passes with no finding
- explicit tutor-role drift hidden under turn-level `mirror_meta.note` is likewise invisible to the current radar collector

This is the same detector field-coverage and narrowness family already tracked by `BUG-17`.

### BUG-106 enrichment: `secret_scanner.py` still misses more standalone secret families and literal prefixes

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round58.md`:
- literal-family false negatives still reproduce for `glpat-...`, `sk_live_...`, `SG....`, `xoxp-...`, and `xoxa-2-...`

This is the same literal-family and stale-pattern defect already tracked by `BUG-106`.

### BUG-107 enrichment: `secret_scanner.py` assignment-style coverage still misses service-specific token labels such as `twilio_auth_token`

Additional evidence folded into `BUG-107` from `XYZGL_new_bug_report_round58.md`:
- `twilio_auth_token=...` still passes cleanly even though it is an obvious assignment-style credential label

This is the same assignment-regex narrowness family already tracked by `BUG-107`.

## Recommended Fix Order For The New Bugs

1. `BUG-125`
2. `BUG-124`

## Preserved Prior Master Body (v17 Combined)# XYZGL Master Bug Report - Final Unified (v17 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v16_20260308_102442.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round57.md`
- `c:\Users\misha\Downloads\xyzgl_bug_findings_20260308_fresh5.zip`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round26.md`
- `c:\Users\misha\Downloads\new_bugs_round30_bundle.zip`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run6.md`

This v17 addendum supersedes the v16 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v16 master: 120
- New unique XYZGL defects added in this update: 3
- Existing bug enrichments added in this update: 9 groups
- Updated open defect total: 123

New defect IDs added here:
- `BUG-121`
- `BUG-122`
- `BUG-123`

## In-Scope Inputs

- `XYZGL_new_bug_report_round57.md`
- `xyzgl_bug_findings_20260308_fresh5.zip`
- `session_state_nondeterminism_findings_round26.md`
- `new_bugs_round30_bundle.zip`
- `new_bugs_grouped_by_file_2026-03-08_run6.md`

## New Defects Added In v17

### BUG-121: Node closure can be forced by keyword-stuffed nonsense because the close gate checks only required-token presence

- **Severity:** High
- **Phase:** 4
- **Source:** `xyzgl_bug_findings_20260308_fresh5.zip`
- **Affected files:**
  - `xyzgl/orchestrator/policies.py`
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** `required_keywords_satisfied()` closes a node once all required keywords or phrases appear in the learner answer, with no check that the answer actually explains the concept or relates the terms coherently. A nonsense reply like `I think 1f 2f gravity you need that.` still yields `NEXT_ACTION: CLOSE_NODE` and advances the session to the next node. That means mastery progression can be unlocked by shallow token stuffing instead of actual understanding.

**Expected:** Node closure requires stronger semantic evidence than raw keyword presence alone. Keyword coverage may be necessary, but it should not be sufficient to certify understanding and advance state.

**Fix:** Strengthen the closure gate to require structured explanation quality, contradiction checks, or a richer eval signal beyond bare keyword inclusion before emitting `CLOSE_NODE`.

---

### BUG-122: `ontario_claims_citation_guard.py` ignores unsupported Ontario/code-specific claims in `session_report.turns[*].eval.gaps`

- **Severity:** High
- **Phase:** 6
- **Source:** `new_bugs_round30_bundle.zip`
- **Affected file:**
  - `tools/ontario_claims_citation_guard.py`

**Problem:** In session mode, the guard scans `teach.teaching_block` and `eval.evaluation` but never scans `eval.gaps`, even though `eval.gaps` is still tutor-authored text that can contain Ontario- or code-specific claims. The supplied repro places `Ontario CSA W47.1 requires continuous visual inspection here.` in `eval.gaps` with no grounding snippets and no citations, yet the tool still returns `PASS` under `--enforce`.

**Expected:** The citation guard scans every tutor-authored text surface that can carry unsupported Ontario/code-specific claims, including `eval.gaps`.

**Fix:** Add `eval.gaps` to the scanned session fields and apply the same citation/grounding checks used for `teach.teaching_block` and `eval.evaluation`.

---

### BUG-123: `reground_cadence_verifier.py` prefers a broken `session_report.json` over a valid `turn_report.json` in the same directory

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_round30_bundle.zip`
- **Affected file:**
  - `tools/reground_cadence_verifier.py`

**Problem:** When the input path is a directory, the tool unconditionally selects `session_report.json` if it exists and only looks at `turn_report.json` when no session artifact is present. A broken or empty witness-wrapped session artifact therefore masks a valid turn artifact in the same directory. The supplied repro shows `session_report.json` causing `could not extract prompt_meta` while a valid `turn_report.json` with `prompt_meta.protocol_regrounded = true` is ignored completely.

**Expected:** Directory-mode verification uses the best valid artifact available, or falls back from a broken session artifact to a valid turn artifact instead of failing early on the first existing filename.

**Fix:** Try session extraction first but fall back to `turn_report.json` when the session artifact cannot be parsed or lacks the required prompt metadata, or validate both artifacts and choose the valid one explicitly.

## Existing Bug Enrichments Added In v17

### BUG-12 enrichment: the default harness still short-circuits normal session probing by manufacturing full-keyword learner answers

Additional evidence folded into `BUG-12` from `session_state_nondeterminism_findings_round26.md`:
- a stock six-turn `harness_session.py` run still emits only `CLOSE_NODE` decisions and never reaches a real `PROBE` path
- the built-in learner answers still embed the active node's full required keyword set on the first attempt

This is the same simulated-learner / unreachable-PROBE defect already tracked by `BUG-12`.

### BUG-13 enrichment: `seed_sweep.py` still presents a vacuous stability result because the sampled per-case seed axis is inert on the shipped stub path

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round26.md`:
- sweeping seeds `1..5` still produced one unique reply hash because the default stub tutor ignores the sampled seed entirely
- the tool therefore proves only that a seed-agnostic stub stayed seed-agnostic, not that the seeded system under test is actually stable

This is the same false-proxy seed-sweep defect family already tracked by `BUG-13`.

### BUG-89 enrichment: default local grounding still injects the lone `demo_fitup` source into unrelated nodes because weak matches are never filtered out

Additional evidence folded into `BUG-89` from `xyzgl_bug_findings_20260308_fresh5.zip`:
- grounded session turns for `pos_1f_vs_2f` and `smaw_basic_arc` still carry `demo_fitup` snippets even though the topic match is unrelated and the retrieval scores are very low
- the shipped default experience therefore still looks grounded in metadata while actually grounding unrelated nodes to the single fit-up demo source

This is the same default-topic collapse and generic-grounding defect already tracked by `BUG-89`.

### BUG-119 enrichment: `targeted_sweep.py` still hides concrete child failure reasons behind generic tail text

Additional evidence folded into `BUG-119` from `new_bugs_grouped_by_file_2026-03-08_run6.md`:
- failing steps such as `doc_code_link_checker`, `coverage_gate`, `backend_fault_injector`, and `mutation_suite` still collapse to tails like `FAIL: wrote outputs to <path>` in `targeted_sweep_report.json`
- the actual failure reasons remain buried only in child-run artifacts, so the top-level sweep report is still not self-sufficient for grouped-by-file triage

This is the same lossy child-diagnostics family already tracked by `BUG-119`.

### BUG-17 enrichment: `protocol_drift_radar.py` still misses plain teaching imperatives when they avoid the current tutor-keyword gate

Additional evidence folded into `BUG-17` from `new_bugs_round30_bundle.zip`:
- a mirror answer like `You should shorten the arc and keep the rod angle steady.` still produces `PASS` with zero findings
- the current mirror-role scan still depends on a narrow pre-gate around words like `tutor`, `lesson`, `learn`, and `practice`, so plain coaching imperatives remain invisible

This is the same detector-narrowness family already tracked by `BUG-17`.

### BUG-66 enrichment: `protocol_drift_radar.py` also ignores tutor-authored `eval.gaps`

Additional evidence folded into `BUG-66` from `new_bugs_round30_bundle.zip`:
- role-drift text placed in `session_report.turns[*].eval.gaps` still yields `PASS` with zero findings
- `_collect_texts()` continues to scan only `teach.teaching_block`, `teach.question`, `eval.evaluation`, and selected mirror text, leaving `eval.gaps` out of the session collector

This is the same session field-coverage defect already tracked by `BUG-66`.

### BUG-40 enrichment: more repo-owned tools still accept malformed `--issue` values and emit schema-invalid bundles

Additional evidence folded into `BUG-40` from `new_bugs_round30_bundle.zip`:
- `repro_backends_smoke.py`, `backend_fault_injector.py`, `retrieval_eval_bench.py`, and `ontario_claims_citation_guard.py` still write bundles successfully under `--issue NOT_AN_ISSUE`
- `validate_schemas.py` then fails their generated `run.json` files because the issue ids violate the repo's own run-meta schema

This is the same malformed-issue acceptance family already tracked by `BUG-40`.

### BUG-106 enrichment: `secret_scanner.py` still misses more standalone secret families and literal prefixes

Additional evidence folded into `BUG-106` from `XYZGL_new_bug_report_round57.md`:
- false negatives still reproduce for `-----BEGIN OPENSSH PRIVATE KEY-----`
- literal token patterns still miss additional GitHub token families such as `ghu_`, `ghs_`, `gho_`, and `ghr_`
- Slack bot tokens like `xoxb-...` still pass cleanly

This is the same literal-family / stale-pattern defect already tracked by `BUG-106`.

### BUG-107 enrichment: `secret_scanner.py` assignment-style coverage still misses standard cloud-secret labels

Additional evidence folded into `BUG-107` from `XYZGL_new_bug_report_round57.md`:
- `AWS_SECRET_ACCESS_KEY=...` still passes cleanly even though it is a standard high-risk secret assignment form

This is the same assignment-regex narrowness family already tracked by `BUG-107`.

## Recommended Fix Order For The New Bugs

1. `BUG-121`
2. `BUG-122`
3. `BUG-123`

## Preserved Prior Master Body (v16 Combined)# XYZGL Master Bug Report - Final Unified (v16 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v15_20260307_202834.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round25.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round25 (1).md`
- `c:\Users\misha\Downloads\new_bugs_round29_bundle.zip`
- `c:\Users\misha\Downloads\new_bugs_grouped_by_file_2026-03-08_run5.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round56.md`

This v16 addendum supersedes the v15 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v15 master: 118
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 5 groups
- Duplicate markdown inputs collapsed: 1
- Updated open defect total: 120

New defect IDs added here:
- `BUG-119`
- `BUG-120`

## In-Scope Inputs

- `session_state_nondeterminism_findings_round25.md`
- `new_bugs_round29_bundle.zip`
- `new_bugs_grouped_by_file_2026-03-08_run5.md`
- `XYZGL_new_bug_report_round56.md`

### Duplicate copy collapsed into the same evidence set
- `session_state_nondeterminism_findings_round25 (1).md`

## New Defects Added In v16

### BUG-119: `targeted_sweep.py` truncates child tool diagnostics too aggressively, so file-grouped findings are silently dropped from the report

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_grouped_by_file_2026-03-08_run5.md`
- **Affected file:**
  - `tools/targeted_sweep.py`

**Problem:** `_tail()` keeps only the last 900 characters of each child tool's stdout before the step result is written. On long `doctor` output this drops earlier file-specific failures, so `targeted_sweep_report.json` can no longer represent the full set of findings grouped by file. The supplied run shows a direct `doctor.py` execution reporting 31 line-budget violations while the corresponding `doctor.stdout_tail` preserved only 19 and begins with an ellipsis, proving earlier diagnostics were discarded before reporting.

**Expected:** The sweep preserves enough child output to support accurate downstream triage, or it stores a structured artifact reference rather than a lossy tail that silently drops earlier findings.

**Fix:** Replace the fixed 900-character tail with a bounded but higher-fidelity capture strategy: store full child artifact paths, preserve both head and tail, or record structured findings separately so long stdout does not erase earlier file-specific diagnostics.

---

### BUG-120: `validate_schemas.py` validates individual JSON files but does not enforce run-bundle completeness

- **Severity:** Medium
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round56.md`
- **Affected file:**
  - `tools/validate_schemas.py`

**Problem:** In run-directory mode, the validator checks only whichever known JSON files happen to exist. It does not require `run.json` to be present, and it does not verify that every path declared in `run.json.outputs` actually exists. As a result, directories with a lone report file and no `run.json`, directories missing declared Markdown summaries, directories missing declared ZIP or binary outputs, and directories missing declared nested child-run artifacts can all still return `PASS: schemas validated`.

**Expected:** Directory validation enforces the repo's run-bundle contract: `run.json` is required, and every declared output path exists regardless of file type.

**Fix:** Require `run.json` for run-directory validation, resolve every entry in `run.json.outputs`, and fail validation when any declared artifact is missing even if schema checks remain JSON-specific.

## Existing Bug Enrichments Added In v16

### BUG-32 enrichment: `harness_session.py` also ignores env-backed tutor and mirror backend selection

Additional evidence folded into `BUG-32` from `session_state_nondeterminism_findings_round25.md`:
- under `DAEDALUS_TUTOR_BACKEND=fault` and `DAEDALUS_FAULT_MODE=exception`, `harness_session.py` still records `teach.prompt_meta.tutor_backend = stub`
- the same environment drives `route_turn()` through the requested `fault` backend and stub fallback path instead

This is the same `XYZGLConfig()` vs `XYZGLConfig.from_env()` root cause already tracked by `BUG-32`, now confirmed to hide env-configured failing backend paths as well as env-configured cadence/path settings.

### BUG-13 enrichment: `seed_sweep.py` still green-lights backend fault fallback because it drops requested/effective backend provenance and backend errors

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round25.md`:
- under `DAEDALUS_TUTOR_BACKEND=fault`, `seed_sweep.py` still reports `PASS` with only fallback `backend = stub` samples
- the saved report omits the requested failing backend, the fallback transition, and any `backend_error`, so a broken backend path can be misclassified as a stable deterministic sweep

This is the same false-proxy and masked-failure family already tracked by `BUG-13`.

### BUG-18 enrichment: the graph checker retry-path `time.sleep` NameError and parse-failure misclassification are independently reconfirmed

Additional evidence folded into `BUG-18` from `new_bugs_round29_bundle.zip`:
- truncated JSON still triggers `details: "name 'time' is not defined"` in the generated report
- the checker also continues into bogus schema-style complaints after the parse failure instead of stopping at the real load error

This is the same malformed-input and wrong-classification defect family already tracked by `BUG-18`.

### BUG-40 enrichment: `graph_invariant_checker.py` also accepts malformed `--issue` values and emits self-invalid bundles

Additional evidence folded into `BUG-40` from `new_bugs_round29_bundle.zip`:
- `graph_invariant_checker.py --issue NOT_AN_ISSUE` still emits a normal bundle whose `run.json` later fails schema validation

This is the same malformed-issue acceptance family already tracked by `BUG-40`.

### BUG-17 enrichment: mirror and protocol detectors still miss schema-valid `eval.mirror_answer` evidence across multiple tools

Additional evidence folded into `BUG-17` from `new_bugs_round29_bundle.zip`:
- `mirror_calibration_bench.py` returns `INCOMPLETE: no mirror answers present` on a schema-valid session where `mirror.answer` is null but `eval.mirror_answer` is populated
- `mirror_leakage_detector.py` misses explicit tutor-role leakage stored only in `eval.mirror_answer`
- `protocol_drift_radar.py` still passes the same explicit tutor-role drift because it never collects `eval.mirror_answer`

This is the same eval/session mirror-answer blind spot already tracked by `BUG-17`.

## Recommended Fix Order For The New Bugs

1. `BUG-120`
2. `BUG-119`

## Preserved Prior Master Body (v15 Combined)# XYZGL Master Bug Report - Final Unified (v15 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v14_20260307_200518.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\round29_new_replay_protocol_bugs.zip`
- `c:\Users\misha\Downloads\new_bugs_round25_bundle.zip`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round51.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round51 (1).md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round20.md`
- `c:\Users\misha\Downloads\session_state_nondeterminism_findings_round20 (1).md`
- `c:\Users\misha\Downloads\new_bug_status_before_phase0_package.zip`
- `c:\Users\misha\Downloads\new_bug_lane_e_forceable_package.zip`
- `c:\Users\misha\Downloads\BUGPACK_v12.4_20260308_010227.zip`

This v15 addendum supersedes the v14 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v14 master: 115
- New unique XYZGL defects added in this update: 3
- Existing bug enrichments added in this update: 5 groups
- Duplicate markdown inputs collapsed: 2
- Out-of-scope prompt-spec / non-XYZGL bundles excluded: 3
- Updated open defect total: 118

New defect IDs added here:
- `BUG-116`
- `BUG-117`
- `BUG-118`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `round29_new_replay_protocol_bugs.zip`
- `new_bugs_round25_bundle.zip`
- `XYZGL_new_bug_report_round51.md`
- `session_state_nondeterminism_findings_round20.md`

### Duplicate copies collapsed into the same evidence set
- `XYZGL_new_bug_report_round51 (1).md`
- `session_state_nondeterminism_findings_round20 (1).md`

### Reviewed and excluded as out-of-scope prompt-spec / non-XYZGL material
- `new_bug_status_before_phase0_package.zip`
- `new_bug_lane_e_forceable_package.zip`
- `BUGPACK_v12.4_20260308_010227.zip`

Reason for exclusion:
- these inputs describe prompt-governance, lane-policy, or phase-state behavior rather than defects in the live XYZGL runtime, harness, replay, audit, or validator codebase

## New Defects Added In v15

### BUG-116: Harness primary report artifacts split identity between filename and declared schema, and `validate_schemas.py` still passes the mismatch

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_round25_bundle.zip`
- **Affected files:**
  - `tools/harness_session.py`
  - `tools/harness_turn.py`
  - `tools/harness_lattice.py`
  - `tools/validate_schemas.py`

**Problem:** `harness_session.py`, `harness_turn.py`, and `harness_lattice.py` write their primary artifacts under `session_report.json`, `turn_report.json`, and `lattice_report.json`, but the top-level documents still declare `schema_version = "witness_event@1"` because the harnesses persist witness envelopes directly under report filenames. `validate_schemas.py` chooses the schema from the filename and never enforces that the document's own `schema_version` matches that filename-selected identity, so all three mismatches still validate as `PASS`.

**Expected:** Primary report filenames carry their own canonical schema identities, or the witness envelope is stored separately under a witness-specific artifact name. Schema validation rejects filename/schema-version disagreements instead of blessing them.

**Fix:** Emit tool-native top-level report payloads under `session_report.json`, `turn_report.json`, and `lattice_report.json`, move witness envelopes into separate witness-named artifacts if they must be preserved, and teach `validate_schemas.py` to enforce filename-to-`schema_version` identity consistency.

---

### BUG-117: `repro_replay_diff.py --strict` false-fails on harmless forward-compatible unknown config keys

- **Severity:** Medium
- **Phase:** 5
- **Source:** `round29_new_replay_protocol_bugs.zip`
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** Turn replay already filters stored config through the recognized `XYZGLConfig` fields before reconstructing runtime behavior, so an unknown future key is intentionally ignored by the actual replay. But strict mode still compares the raw stored config dictionary against the replayed config dictionary, which drops that unknown key. As a result, a harmless forward-compatible field like `payload.turn_result.config.future_flag = "ignored-by-runtime"` causes a strict `FAIL` even though runtime behavior is unchanged and the field is semantically inert.

**Expected:** Strict replay compares effective runtime semantics or otherwise distinguishes inert forward-compatible metadata from behavior-changing configuration drift.

**Fix:** Normalize both stored and replayed config through the same recognized-key filter before strict comparison, or classify ignored extra keys as non-fatal compatibility notes rather than hard replay failures.

---

### BUG-118: `protocol_drift_radar.py` can hide later HIGH findings behind earlier WARN spam because `MAX_FINDINGS` is severity-insensitive

- **Severity:** High
- **Phase:** 6
- **Source:** `round29_new_replay_protocol_bugs.zip`
- **Affected file:**
  - `tools/protocol_drift_radar.py`

**Problem:** `_findings()` stops scanning as soon as `len(out) >= MAX_FINDINGS`. If enough earlier mirror text produces WARN findings, later HIGH-severity tutor-role drift never gets processed at all. The supplied repro shows 250 early turns consuming the full 1,000-finding budget with WARN entries, after which a final explicit HIGH tutor self-mislabel in `teach.question` is skipped entirely and the tool returns `PASS` with `HIGH=0`.

**Expected:** High-severity protocol drift is never masked by lower-severity noise. Caps should preserve severity ordering or summarize overflow without suppressing later HIGH evidence.

**Fix:** Make the findings budget severity-aware, continue scanning after WARN saturation while reserving space for HIGH findings, or compute severity counts first and truncate only the serialized tail after preserving the highest-severity items.

## Existing Bug Enrichments Added In v15

### BUG-107 enrichment: `secret_scanner.py` still misses more underscore, hyphenated, and composite credential labels

Additional evidence folded into `BUG-107` from `XYZGL_new_bug_report_round51.md`:
- false negatives still reproduce for `private_key`, `client-key`, `access-key`, `signingSecret`, `bot_token`, `clientSecretKey`, `apiTokenSecret`, and `jwt_key`

This is the same assignment-regex narrowness family already tracked by `BUG-107`.

### BUG-110 enrichment: stale grounding cache is independently reconfirmed under in-process source edits

Additional evidence folded into `BUG-110` from `session_state_nondeterminism_findings_round20.md`:
- grounded prompts in the same Python process still return the old manifest-listed snippet after the source file is overwritten, as long as `manifest.json` itself is unchanged

This is the same corpus-cache invalidation failure already tracked by `BUG-110`.

### BUG-111 enrichment: strict session replay still ignores session-level control metadata such as `payload.session_report.max_turns`

Additional evidence folded into `BUG-111` from `round29_new_replay_protocol_bugs.zip`:
- tampering stored `payload.session_report.max_turns` from `256` to `999` still yields `PASS` and `--strict PASS`
- session replay reuses the forged value, `run_session()` internally caps it back down, and the comparer still checks only the hash of `turns`

This is the same replay-contract omission family already tracked by `BUG-111`, now confirmed on session-level control metadata as well as witness identity fields.

### BUG-66 enrichment: `protocol_drift_radar.py` also ignores session `node_title`

Additional evidence folded into `BUG-66` from `round29_new_replay_protocol_bugs.zip`:
- explicit high-signal role-drift text placed in `turns[0].node_title` still yields `PASS` with zero findings
- moving the same text into scanned `teach.question` flips the control case to `FAIL`

This is the same session collector field-coverage defect already tracked by `BUG-66`, now confirmed to extend beyond `eval.next_action` to `node_title` as well.

### BUG-13 enrichment: `seed_sweep.py` still is not bit-for-bit reproducible even when analytical content is unchanged

Additional evidence folded into `BUG-13` from `session_state_nondeterminism_findings_round20.md`:
- two identical `seed_sweep.py` runs with identical inputs produced identical samples but different time-based `run_id` values
- the same report notes `harness_session.py` inherits the same replayability issue when `--run-id` is omitted and the tool falls back to `make_run_id()`

This remains the same artifact-stability and replay-noise family already tracked by `BUG-13`.

## Recommended Fix Order For The New Bugs

1. `BUG-118`
2. `BUG-116`
3. `BUG-117`

## Preserved Prior Master Body (v14 Combined)# XYZGL Master Bug Report - Final Unified (v14 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v13_20260307_194830.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round50.md`
- `c:\Users\misha\Downloads\graph_mirror_round20_report.zip`
- `c:\Users\misha\Downloads\new_bugs_round24_bundle.zip`
- `c:\Users\misha\Downloads\round30_ci_gate_session_dir_fix_patch.zip`
- `c:\Users\misha\Downloads\new_bug_brain_diff_checkpoint_package.zip`
- `c:\Users\misha\Downloads\new_bug_overridecanon_intent_package.zip`
- `c:\Users\misha\Downloads\BUGPACK_v12.3_20260308_005659.zip`

This v14 addendum supersedes the v13 count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v13 master: 113
- New unique XYZGL defects added in this update: 2
- Existing bug enrichments added in this update: 7 groups
- Patch-only context bundles reviewed: 1
- Out-of-scope prompt-spec / CompanionWriter bundles excluded: 3
- Updated open defect total: 115

New defect IDs added here:
- `BUG-114`
- `BUG-115`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `XYZGL_new_bug_report_round50.md`
- `graph_mirror_round20_report.zip`
- `new_bugs_round24_bundle.zip`

### Patch-only context
- `round30_ci_gate_session_dir_fix_patch.zip`
  - maps to existing `BUG-76`

### Reviewed and excluded as out-of-scope prompt-spec / CompanionWriter material
- `new_bug_brain_diff_checkpoint_package.zip`
- `new_bug_overridecanon_intent_package.zip`
- `BUGPACK_v12.3_20260308_005659.zip`

Reason for exclusion:
- these inputs describe prompt-governance, canon-state, or CompanionWriter/Apex control-plane issues rather than defects in the live XYZGL runtime, harness, grounding, replay, or validator codebase

## New Defects Added In v14

### BUG-114: `coverage_gate.py` can fail for smoke-test reasons while falsely reporting that numeric coverage thresholds were not met

- **Severity:** Medium
- **Phase:** 6
- **Source:** `new_bugs_round24_bundle.zip`
- **Affected file:**
  - `tools/coverage_gate.py`

**Problem:** `coverage_gate.py` computes `ok` as a combined condition over line coverage, branch coverage, and `smoke_failures`, but the summary text still reports `FAIL: thresholds not met` even when both configured numeric thresholds were exceeded. In the reproduced run, line and branch coverage were both above the configured minimums, yet the tool failed because `smoke_failures=["repro_backends_smoke"]` and still described the failure as a threshold miss.

**Expected:** The tool reports the actual failure reason. Numeric threshold failures and unrelated smoke-step regressions are distinguished in both machine-readable and human-readable outputs.

**Fix:** Split the failure classification so numeric threshold misses, smoke regressions, and mixed failures produce distinct statuses/messages instead of reusing the same `thresholds not met` text for every non-pass outcome.

---

### BUG-115: `graph_invariant_checker.py` and `mirror_leakage_detector.py` leak absolute local filesystem paths into generated reports

- **Severity:** Low
- **Phase:** 6
- **Source:** `graph_mirror_round20_report.zip`
- **Affected files:**
  - `tools/graph_invariant_checker.py`
  - `tools/mirror_leakage_detector.py`

**Problem:** Generated report artifacts persist absolute local paths such as the full repo-root `runs/...` path and the absolute path to `session_report.json`. This leaks local filesystem layout and makes bundles less portable for sharing, replay, and comparison across machines.

**Expected:** Tool reports store relative paths, logical artifact identifiers, or sanitized placeholders rather than absolute local paths.

**Fix:** Rewrite stored source/path fields to repository-relative or run-relative paths before serialization, or omit them when a stable relative form cannot be produced.

## Existing Bug Enrichments Added In v14

### BUG-107 enrichment: `secret_scanner.py` still misses broader camelCase credential labels

Additional evidence folded into `BUG-107` from `XYZGL_new_bug_report_round50.md`:
- enforce-mode false negatives still reproduce for `appKey=...`, `authSecret=...`, `bearerToken=...`, `webhookKey=...`, `serviceKey=...`, `oauthSecret=...`, `jwtSecret=...`, and `privateSecret=...`

This is the same assignment-regex narrowness family already tracked by `BUG-107`.

### BUG-17 enrichment: mirror leakage detection still misses baseline tutor-shaped mirror guidance and more imperative variants

Additional evidence folded into `BUG-17` from `graph_mirror_round20_report.zip`:
- a live baseline harness session still produced tutor-shaped mirror answers such as `Share: material thickness, process, and what defect you see.` and `Try adjusting your travel angle and watch the puddle.` while `mirror_leakage_detector.py` returned `PASS`
- the same audit confirms more imperative starter blind spots such as `share`, `try`, `check`, `adjust`, `watch`, `focus on`, `start by`, and `stop and`

This remains the same detector phrase-coverage defect already tracked in the master.

### BUG-04 enrichment: baseline harness runs still reproduce tutor-shaped stub mirror behavior

Additional evidence from `graph_mirror_round20_report.zip` reconfirms that ordinary baseline harness sessions still emit instructive mirror text like `I think: Stop and correct fit-up before welding...` and `I think: I hear you. Share: material thickness...`. That behavior is the same underlying learner-simulation failure already tracked by `BUG-04`.

### BUG-18 enrichment: graph invariant checking still fails open on more malformed graph shapes and still mishandles invalid JSON

Additional evidence folded into `BUG-18`:
- `graph_mirror_round20_report.zip` shows `graph_invariant_checker.py` silently dropping non-dict `nodes[]` entries and returning `PASS`
- the same audit reconfirms the malformed-JSON retry/import path (`time.sleep(...)` without `import time`) and the wrong final classification after load failure
- `new_bugs_round24_bundle.zip` independently reconfirms the same malformed-JSON retry-path defect

These are all the same graph-checker validation and error-path failures already tracked by `BUG-18`.

### BUG-34 enrichment: `property_turn_fuzzer.py` non-canonical `run.json` still reproduces under strict artifact round-tripping

Additional evidence folded into `BUG-34` from `new_bugs_round24_bundle.zip`:
- `artifact_roundtrip.py --strict` still fails on a repo-emitted property-fuzzer bundle because `run.json` is not canonical

This remains the same non-canonical `property_turn_fuzzer.py` artifact bug already tracked in the master.

### BUG-78 enrichment: `coverage_gate.py` non-canonical `coverage_raw.json` still reproduces under strict artifact round-tripping

Additional evidence folded into `BUG-78` from `new_bugs_round24_bundle.zip`:
- `artifact_roundtrip.py --strict` still fails on a repo-emitted coverage bundle because `coverage_raw.json` is not canonical

This remains the same non-canonical coverage artifact bug already tracked in the master.

### BUG-113 enrichment: grounding/protocol smoke artifact mislabeling is independently reconfirmed

Additional evidence folded into `BUG-113` from `new_bugs_round24_bundle.zip`:
- `repro_grounding_protocol_smoke.py` still emits `ci_gate_report.json` with `schema_version = ci_gate_report@1` even though the reported steps are grounding/protocol smoke steps rather than CI-gate stages

This is the same cross-tool artifact-identity drift already tracked by `BUG-113`.

## Patch-Only Context

### BUG-76 patch context: `round30_ci_gate_session_dir_fix_patch.zip`

The supplied patch zip updates `tools/ci_gate.py` to fall back to scanning its dedicated `child_runs/` directory when stdout path parsing cannot recover `session_run_dir`. That maps directly to the already-tracked `BUG-76` failure mode and was not counted as a new defect.

## Recommended Fix Order For The New Bugs

1. `BUG-114`
2. `BUG-115`

## Preserved Prior Master Body (v13 Combined)
# XYZGL Master Bug Report - Final Unified (v13 Combined)

## Scope

This report extends the supplied flattened master:
- `c:\Users\misha\Downloads\XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v12_COMBINED_20260307_1.md`

New inputs reviewed for this update:
- `c:\Users\misha\Downloads\arcvulcan_new_bugs_round22.zip`
- `c:\Users\misha\Downloads\arcvulcan_new_bugs_round23.zip`
- `c:\Users\misha\Downloads\round25_new_replay_protocol_bugs.zip`
- `c:\Users\misha\Downloads\xyzgl_new_bug_report_27th_pass_2026-03-07.md`
- `c:\Users\misha\Downloads\XYZGL_new_bug_report_round48.md`
- `c:\Users\misha\Downloads\graph_mirror_audit_round28_20260307.zip`
- `c:\Users\misha\Downloads\new_bug_deliverable_only_vs_canon_prompting_package.zip`
- `c:\Users\misha\Downloads\new_bug_recalibrate_brain_reset_package.zip`
- `c:\Users\misha\Downloads\new_bug_project_alias_drift_package.zip`
- `c:\Users\misha\Downloads\new_bug_lane_persistence_package.zip`
- `c:\Users\misha\Downloads\BUGPACK_v11.9_20260308_001803.zip`

This v13 addendum supersedes the v12 combined count summary at the top of the preserved body below.

## Delta Summary

- Prior open defects in supplied v12 combined master: 108
- New unique XYZGL defects added in this update: 5
- Existing bug enrichments added in this update: 6 groups
- Out-of-scope prompt-spec / CompanionWriter bundles excluded: 5
- Updated open defect total: 113

New defect IDs added here:
- `BUG-109`
- `BUG-110`
- `BUG-111`
- `BUG-112`
- `BUG-113`

## In-Scope vs Excluded Inputs

### In-scope XYZGL inputs
- `arcvulcan_new_bugs_round22.zip`
- `arcvulcan_new_bugs_round23.zip`
- `round25_new_replay_protocol_bugs.zip`
- `xyzgl_new_bug_report_27th_pass_2026-03-07.md`
- `XYZGL_new_bug_report_round48.md`
- `graph_mirror_audit_round28_20260307.zip`

### Reviewed and excluded as out-of-scope prompt-spec / CompanionWriter material
- `new_bug_deliverable_only_vs_canon_prompting_package.zip`
- `new_bug_recalibrate_brain_reset_package.zip`
- `new_bug_project_alias_drift_package.zip`
- `new_bug_lane_persistence_package.zip`
- `BUGPACK_v11.9_20260308_001803.zip`

Reason for exclusion:
- these bundles describe prompt-governance, story-state, or CompanionWriter/Apex control-plane issues rather than defects in the live XYZGL runtime, harness, grounding, replay, or validator codebase

## New Defects Added In v13

### BUG-109: `DAEDALUS_MIRROR_SEND_USER_CONTENT=1` reports `prompt_mode="raw"` but router mirror input is still sanitized

- **Severity:** Medium
- **Phase:** 1
- **Source:** `arcvulcan_new_bugs_round22.zip`
- **Affected file:**
  - `xyzgl/router.py`

**Problem:** `xyzgl.router._mirror_context_block()` always sanitizes the learner text before returning it, even when `DAEDALUS_MIRROR_SEND_USER_CONTENT=1` sets mirror metadata to `prompt_mode="raw"`. The runtime therefore promises raw mirror context while actually sending sanitized content.

**Expected:** Either `send_raw=True` actually sends bounded raw text, or the metadata reports the mode honestly instead of claiming `raw`.

**Fix:** Make `_mirror_context_block(send_raw=True)` bypass sanitization while keeping the existing length cap, or rename the recorded mode to match the sanitized behavior.

---

### BUG-110: Grounding corpus cache ignores manifest-listed source edits and deletions until manifest churn or process restart

- **Severity:** High
- **Phase:** 2
- **Source:** `arcvulcan_new_bugs_round23.zip`
- **Affected file:**
  - `xyzgl/grounding/prompting.py`

**Problem:** `_cached_corpus()` invalidates the grounding cache using only `manifest.json` metadata. Editing or deleting a manifest-listed source file does not invalidate `_CORPUS_CACHE`, so grounded prompts can keep serving stale or revoked content until `manifest.json` changes or the process restarts.

**Expected:** Cache invalidation covers the full manifest-listed corpus, including each referenced source path plus its existence, mtime, and size.

**Fix:** Replace the manifest-only cache signature with a corpus signature built from `manifest.json` and every manifest-listed source file.

---

### BUG-111: `repro_replay_diff.py --strict` still ignores witness identity fields such as outer envelope metadata and `turn_index`

- **Severity:** Medium
- **Phase:** 5
- **Source:** `round25_new_replay_protocol_bugs.zip`
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** Strict replay still returns `PASS` when a turn bundle's top-level witness envelope fields (`issue_id`, `event_id`, `created_at`) are forged, and it also ignores drift in `payload.turn_result.turn_index`. These fields are part of the recorded witness contract, but replay validation does not compare them.

**Expected:** Strict replay fails when canonical witness envelope identity or recorded turn ordering drifts from the replayed artifact.

**Fix:** Include top-level witness envelope fields and `payload.turn_result.turn_index` in the strict comparison set for turn bundles.

---

### BUG-112: `validate_schemas.py` has incomplete shipped-schema coverage in both direct-file and run-directory validation modes

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_27th_pass_2026-03-07.md`
- **Affected file:**
  - `tools/validate_schemas.py`

**Problem:** The validator cannot auto-infer the shipped schema for a direct `prompt_snapshots.json` file even though the repo ships `schemas/prompt_snapshots.schema.json`. In run-directory mode it also skips invalid `coverage_raw.json` and `lattice_crash.json` artifacts, allowing `PASS: schemas validated` on directories that contain malformed JSON for shipped outputs.

**Expected:** Direct-file validation recognizes shipped filenames without requiring `--schema`, and run-directory validation inspects every shipped artifact emitted by the corresponding producer tools.

**Fix:** Add direct mapping for `prompt_snapshots.json` and extend run-directory artifact coverage to `coverage_raw.json` and `lattice_crash.json`.

---

### BUG-113: Repro smoke tools emit other tools' report names and schema versions, and `validate_schemas.py` blesses the mismatch as canonical

- **Severity:** Medium
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round48.md`
- **Affected files:**
  - `tools/repro_grounding_protocol_smoke.py`
  - `tools/repro_backends_smoke.py`
  - `tools/validate_schemas.py`

**Problem:** `repro_grounding_protocol_smoke.py` writes `ci_gate_report.json` with `schema_version = "ci_gate_report@1"`, and `repro_backends_smoke.py` writes `backend_fault_report.json` with `schema_version = "backend_fault_report@1"`. Those artifacts impersonate other tools' report contracts. `validate_schemas.py` currently treats both mislabeled pairs as valid, so the validator locks the contract drift in place instead of catching it.

**Expected:** Each producer emits a tool-specific report filename and schema version, and schema validation rejects cross-tool report/schema impersonation.

**Fix:** Rename both repro smoke report artifacts to tool-specific names, introduce dedicated schema versions, and update `validate_schemas.py` so the old mislabeled pairs fail validation.

## Existing Bug Enrichments Added In v13

### BUG-05 enrichment: mirror redaction still misses Gemini-style header secrets

Additional evidence folded into `BUG-05` from `arcvulcan_new_bugs_round22.zip`:
- default redacted mirror mode still leaks `X-Goog-Api-Key:` header values because the header-redaction list covers `authorization`, `cookie`, `set-cookie`, and `x-api-key` but not `x-goog-api-key`

This is the same redacted-mirror content leak already tracked by `BUG-05`.

### BUG-17 enrichment: detector phrase coverage and scanned-field coverage remain too narrow

Additional evidence folded into `BUG-17`:
- `graph_mirror_audit_round28_20260307.zip` shows `mirror_leakage_detector.py` still passing tutor-shaped mirror text such as `Start with ...` and `One tip: ...`
- the same audit shows fail-open behavior when `mirror.answer` is falsey or non-string and the leaky text sits in `eval.mirror_answer`
- `round25_new_replay_protocol_bugs.zip` shows `protocol_drift_radar.py` still passing `I am the learner in this exchange.` and `I'll coach you through this step by step, then grade your answer.`

This remains the same detector narrowness / missing-surface bug family already tracked in the master.

### BUG-18 enrichment: graph invariant checking still diverges from real graph-core normalization in both directions

Additional evidence folded into `BUG-18` from `graph_mirror_audit_round28_20260307.zip`:
- list-valued `title` still passes even though runtime round-trip stringifies it
- list-valued `summary` still passes even though runtime round-trip stringifies it
- `confidence: null` still false-fails even though runtime normalizes it to `0.0`
- `last_verified_turn: null` still false-fails even though runtime normalizes it to `-1`

This is the same checker/runtime divergence family already tracked by `BUG-18`.

### BUG-105 enrichment: workflow-tool structured-input validation is still incomplete

Additional evidence folded into `BUG-105` from `xyzgl_new_bug_report_27th_pass_2026-03-07.md`:
- `apply_signal_fidelity_overlay.py` still returns `PASS` for an empty overlay directory that copies zero files
- `signal_fidelity_port.py` silently accepts duplicate-key plan JSON instead of rejecting the malformed control input
- `signal_fidelity_port.py` still hard-crashes with `KeyError: 'to'` when a plan action omits `to`

These are all the same malformed-or-no-op structured-input failures already tracked in `BUG-105`.

### BUG-26 enrichment: protocol drift tail-position misses are joined by additional phrasing misses, not a new bug family

Additional evidence from `round25_new_replay_protocol_bugs.zip` confirms more role-drift phrasing escapes the current detector model. These were folded into `BUG-17`, while the current bundle's replay-comparison gaps became `BUG-111`.

### BUG-110 note: stale grounding cache was not present as an explicit open bug in the supplied v12 combined base

The stale cache behavior reported by `arcvulcan_new_bugs_round23.zip` has therefore been added as a new master defect here rather than treated as an enrichment.

## Recommended Fix Order For The New Bugs

1. `BUG-110`
2. `BUG-113`
3. `BUG-112`
4. `BUG-111`
5. `BUG-109`

## Preserved Prior Master Body (v12 Combined)
# XYZGL Master Bug Report ??? Final Unified (v12 Combined)

## Scope

This report is the single authoritative, flattened, deduplicated XYZGL defect list. It merges:

1. **XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v11** (108 open defects, BUG-01 through BUG-108)
2. **COMBINED_BUG_REPORT_ROUND22_31_45_AND_PROMOTE_WITH_BUGPACK_V11_5** (5 XYZGL findings from three source reports)

All nested "Preserved Prior Master Body" layers have been flattened into this single document. Enrichments from later rounds are folded directly into each bug's description or listed in the enrichment log.

### Deduplication Results

| COMBINED Finding | Disposition | Merged Into |
|-----------------|-------------|-------------|
| C-BUG-01 (replay ignores broken mirror paths) | Duplicate | BUG-16 |
| C-BUG-02 (drift radar clips at 4000 chars) | Duplicate | BUG-26 |
| C-BUG-03 (drift radar misses short imperatives) | Duplicate | BUG-17 |
| C-BUG-04 (turn-0 protocol crowds out USER block) | Duplicate | BUG-03 |
| C-BUG-05 (secret_scanner label variants) | Enrichment | BUG-107 |

All 5 XYZGL findings mapped to existing master bugs. No new defect IDs were added.

**Non-XYZGL bundles:** `new_bug_promote_command_package.zip` (canon-governance command spec) and `BUGPACK_v11.5` (CompanionWriter/Apex) were reviewed and excluded from XYZGL defect counts.

## Updated Executive Summary

| Category | Count | Severity Breakdown |
|----------|-------|------|
| A. Runtime Core (Router / Orchestrator / Mirror) | 14 | 14 High |
| B. Session Orchestration | 4 | 2 High, 2 Medium |
| C. Single-Turn Harness & Artifacts | 7 | 2 High, 5 Medium |
| D. Session Harness & Sweep Stability | 10 | 2 High, 8 Medium |
| E. Replay Diff Tool | 8 | 2 High, 6 Medium |
| F. Detection & Quality Gates | 34 | 9 High, 24 Medium, 1 Low |
| G. Grounding & Retrieval Integrity | 13 | 13 High |
| H. Findings From Combined Reports | 18 | 7 High, 9 Medium, 2 Low |
| **Total open** | **108** | **53 High, 52 Medium, 3 Low** |

Additionally, 3 issues were already resolved by Round 33 patches (see Appendix A).

## Fix Sequence

Fixes are ordered into seven phases based on severity, dependency chains, and the principle that runtime correctness must land before tooling that validates it.

### Phase 1 ???????? Runtime Safety and Data Handling

| Bug | Title |
|-----|-------|
| BUG-01 | Non-strict tutor backend fallback is unreachable |
| BUG-02 | Router does not enforce the reply contract |
| BUG-05 | Mirror redaction mode leaks excerpts |
| BUG-06 | Raw mirror mode permits delimiter injection |
| BUG-27 | Invalid protocol paths silently downgrade to fallback |
| BUG-28 | Mirror empty-response treated as success |
| BUG-54 | Empty tutor output silently accepted in probe/eval phases |

### Phase 2 ???????? Mirror Runtime & Grounding Integrity

| Bug | Title |
|-----|-------|
| BUG-04 | StubMirrorBackend emits tutor-style language |
| BUG-03 | Prompt-budget pressure can erase the user block / leave half-open grounding |
| BUG-19 | Grounding assembly stops at first oversized header |
| BUG-20 | Absolute grounding paths silently disable grounding |
| BUG-21 | Grounding retrieval is poisonable |
| BUG-58 | Grounding headers trust raw manifest source_id and source_title |
| BUG-69 | Oversized grounding manifests silently disable grounding |
| BUG-70 | Hard no-overlap chunk splitting breaks retrieval at boundaries |

### Phase 3 ???????? Session Orchestration

| Bug | Title |
|-----|-------|
| BUG-07 | Session loop has no terminal condition after mastery |
| BUG-08 | Node selection ignores seed and starves tied nodes |
| BUG-09 | Session loses conversational continuity across turns |

### Phase 4 ???????? Harness & Determinism

| Bug | Title |
|-----|-------|
| BUG-10 | harness_turn crashes on failure / lone-surrogate Unicode |
| BUG-11 | harness_turn leaks sensitive input into artifacts |
| BUG-23 | Turn artifacts do not record model-facing input |
| BUG-24 | turn_summary.md is artifact-unsafe and uncapped |
| BUG-37 | harness_turn hides mirror-path output from summary |
| BUG-12 | Session harness does not exercise PROBE; simulated learner ignores context |
| BUG-13 | Session/sweep artifacts are not byte-stable; seed_sweep is a false proxy |
| BUG-32 | harness_session ignores env-backed protocol reground cadence |
| BUG-33 | harness_session ignores env-backed protocol and grounding paths |
| BUG-43 | GWEN_DISABLED is a dead isolation switch |
| BUG-49 | harness_turn treats empty tutor reply as PASS |
| BUG-50 | Mirror enablement and privacy controls not propagated across session tooling |
| BUG-52 | seed_sweep run identity tied to --seed, not workload |
| BUG-55 | run_paths.py resolves runs root against caller CWD |
| BUG-60 | Invalid DAEDALUS_RUNS_DIR overrides silently ignored |
| BUG-62 | harness_turn artifacts not self-describing for env-only and fault-injection runs |

### Phase 5 ???????? Replay & Drift Tooling

| Bug | Title |
|-----|-------|
| BUG-14 | repro_replay_diff reconstructs prompts differently from harness |
| BUG-15 | repro_replay_diff masks session failures in mixed directories |
| BUG-16 | repro_replay_diff ignores turn-level mirror, fallback, and backend provenance drift |
| BUG-31 | targeted_sweep does not forward --allow-external-path |
| BUG-45 | targeted_sweep sanitizes child output before extracting run paths |
| BUG-65 | repro_replay_diff ignores sibling turn_summary.md input drift |
| BUG-67 | targeted_sweep contaminates repo before running doctor |
| BUG-72 | repro_replay_diff ignores sibling knowledge_graph.json drift |

### Phase 6 ???????? Detection Tools & Quality Gates

| Bug | Title |
|-----|-------|
| BUG-17 | Mirror/drift detection tools are too narrow and fragile |
| BUG-18 | Graph invariant checker fail-opens on malformed input |
| BUG-22 | Quality gates (selfcheck + mutation suite) are stale |
| BUG-25 | property_turn_fuzzer under-validates and omits failing payloads |
| BUG-26 | protocol_drift_radar has a tail-position blind spot |
| BUG-29 | backend_contract_probe accepts empty backend output |
| BUG-30 | backend_fault_injector has a false-positive hole |
| BUG-34 | property_turn_fuzzer writes non-canonical run.json |
| BUG-35 | Turn fuzzer cannot reach welding-specific branch |
| BUG-36 | Turn fuzzer cannot generate control/Unicode stressors |
| BUG-38 | prompt_snapshot_guard silently rewrites baseline without --update |
| BUG-39 | backend_contract_probe falsely fails supported slow fault mode |
| BUG-40 | Multiple tools accept malformed --issue IDs |
| BUG-41 | latency_cost_budget_enforcer is not hermetic |
| BUG-42 | grounding_injection_audit is environment-sensitive |
| BUG-44 | property_turn_fuzzer truncates evidence and changes schema on incomplete path |
| BUG-46 | 500-source corpus cap silently drops relevant sources |
| BUG-47 | 20,000-passage cap exhausted by filler before target loads |
| BUG-48 | Duplicate root keys in manifest.json zero out corpus |
| BUG-51 | backend_contract_probe accepts spoofed backend identity |
| BUG-53 | signal_fidelity_port.py missing required companion docs |
| BUG-56 | backend_contract_probe can pass without probing any backend |
| BUG-57 | backend_contract_probe accepts boolean latency_ms |
| BUG-59 | retrieval_eval_bench accepts symlink corpora that runtime rejects |
| BUG-61 | harness_turn --keep-storage is a dead flag |
| BUG-63 | ai_property_turn_fuzzer.md is out of sync with tool outputs |
| BUG-64 | secret_scanner silently skips large text files |
| BUG-66 | protocol_drift_radar never scans session eval.next_action |
| BUG-68 | property_turn_fuzzer overstates coverage when --max-len=0 |
| BUG-71 | mirror_leakage_detector accepts arbitrary top-level JSON with turns |
| BUG-73 | protocol_drift_radar ignores session_summary.md in directory scans |

---


## A. Runtime Core ??? Router / Orchestrator / Mirror

### BUG-01: Non-strict tutor backend fallback is unreachable

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/router.py` ???????? `strict_tutor = require_real_backends() or _is_real_tutor_backend(cfg.tutor_backend)`
  - `xyzgl/orchestrator/tutor_phases.py` ???????? duplicated `_is_real_tutor_backend()` and identical logic

**Problem:** `strict_tutor` evaluates to `True` for any non-stub backend name, even when `DAEDALUS_REQUIRE_REAL_BACKENDS` is not set. Missing Gemini credentials or unknown backend names raise instead of degrading to stub. Mirror-side faults degrade correctly, confirming the inconsistency is tutor-specific. Workflow tools (`repro_backends_smoke.py`, `backend_fault_injector.py`) continue to reproduce this in current rounds.

**Expected:** Only `DAEDALUS_REQUIRE_REAL_BACKENDS=1` makes tutor faults fatal.

**Fix:** Use `require_real_backends()` alone for strictness in both router and tutor_phases paths.

---

---

### BUG-02: Router does not enforce the reply contract after tutor generation

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/router.py` ???????? `reply = _clamp(tutor_res.text or "", out_limit)`
  - `xyzgl/config.py` ???????? `max_chars_out` validation
  - `xyzgl/orchestrator/tutor_phases.py` ???????? teach-phase accepts empty tutor response and returns blank `teaching_block`

**Problem:** Empty tutor replies are not treated as backend failures. `max_chars_out` can truncate the mandatory `Safety first: ` prefix. With `DAEDALUS_TUTOR_BACKEND=fault` and `DAEDALUS_FAULT_MODE=empty`, the router returns `reply: ""` and `effective_backend: "tutor_fault"` without setting `backend_error`. Strict mode also allows this through. The teach-phase orchestrator has the same blind spot.

**Expected:** Non-strict empty replies fall back to stub. Strict mode raises on empty contract results. Config floors `max_chars_out` to at least `len(SAFETY_PREFIX)`. Teach-phase treats empty tutor response as backend failure.

**Fix:** After generation: ensure non-empty body, re-apply `Safety first: ` if missing, then clamp. Floor `max_chars_out`. Apply the same empty-reply guard in both router and tutor_phases paths.

---

---

### BUG-03: Prompt-budget pressure can erase the user block and leave half-open structural markers

- **Severity:** High
- **Phase:** 2
- **Affected files:**
  - `xyzgl/prompting.py` ???????? `build_tutor_prompt()`, `_join_parts_bounded()`
  - `xyzgl/backends/stub.py` ???????? user block extraction

**Problem:** User block is appended last. Large protocol or grounding content can consume the budget before it is emitted. Under moderate budgets the prompt can include `<<<DAEDALUS_GROUNDING>>>` but truncate before `<<<END_DAEDALUS_GROUNDING>>>` and before any USER block, leaving a half-open structural marker. The stub backend returns empty input if user markers are missing. Additionally, `_sanitize_user_text(...)` can expand marker-heavy user text after budgeting (e.g. `<<<USER>>>` becomes `<USER_OPEN>`), and the final `_join_parts_bounded(..., max_chars=prompt_budget)` can then clip off `USER_CLOSE`, corrupting the structured prompt boundary.

**Expected:** The user section is always preserved; optional protocol/grounding blocks are truncated first. Required structural markers are never left unclosed. Budget cap is applied after sanitization, not only before.

**Fix:** Reserve prompt budget for all required structural markers and the final USER section before adding optional protocol/grounding payloads. Re-apply the cap after sanitization, not only before it.

---

---

### BUG-04: StubMirrorBackend emits tutor-style imperative language

- **Severity:** High
- **Phase:** 2
- **Affected file:**
  - `xyzgl/backends/stub.py` ???????? mirror generation reuses `tutor_reply()`, strips `Safety first:`, prepends `I think:`

**Problem:** The mirror backend simulates the learner but structurally reuses tutor output. Happy-path mirror answers include tutor imperatives like `I think: Stop and correct fit-up before welding...`.

**Expected:** Mirror output should be tentative, first-person, learner-shaped, and non-imperative.

**Fix:** Stop reusing `tutor_reply()` for mirror generation. Build mirror text from topic/question cues and emit learner-style summaries.

---

---

### BUG-05: Mirror redaction mode still leaks prompt content via excerpts

- **Severity:** High
- **Phase:** 1
- **Affected file:**
  - `xyzgl/router.py` ???????? `_mirror_context_block()`: in redacted mode, returns `excerpt={cleaned[:160]}`

**Problem:** The mirror prompt claims to be redacted but still includes a 160-character content excerpt. `_sanitize_text()` only redacts pattern-matched secrets; ordinary PII passes through. The excerpt can also contain injected `Tutor replied:` delimiters, making redacted mode boundary-injectable.

**Expected:** Redacted mode exposes only structural metadata (length, digest), no text excerpts.

**Fix:** Remove the excerpt from redacted mirror blocks entirely. Keep only `len=` and `digest=` metadata.

---

---

### BUG-06: Raw mirror mode permits delimiter injection

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/router.py` ???????? mirror prompt assembled with plain-text `Learner said:` / `Tutor replied:` delimiters
  - `xyzgl/backends/stub.py` ???????? extracts learner text by stopping at first `Tutor replied:`

**Problem:** A learner message containing `Tutor replied:` can truncate or reshape the extracted learner segment.

**Expected:** Prompt boundaries should be encoded in a non-injectable format.

**Fix:** Use structured encoding or escape reserved delimiter tokens before prompt assembly.

---

---

### BUG-27: Invalid protocol paths silently downgrade to the fallback protocol

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/protocols.py` ???????? `load_protocol_text()` converts path resolution, existence, and read failures into `_fallback_bundle()`
  - `xyzgl/prompting.py` ???????? reports `protocol_regrounded=True`; no metadata distinguishes full load from fallback downgrade

**Problem:** Absolute, missing, or otherwise invalid protocol paths silently remove most intended role guardrails. Downstream tools see a regrounding signal even though only the tiny fallback contract was injected.

**Expected:** Protocol-load failures are surfaced explicitly in prompt metadata.

**Fix:** Surface protocol-load failures explicitly. Fail closed or mark the prompt as fallback-regrounded.

---

---

### BUG-28: Mirror empty-response paths are treated as success

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/router.py` ???????? mirror handling accepts `mres.text or ""`
  - `xyzgl/orchestrator/mirror.py` ???????? returns `res.text` without treating empty text as backend failure

**Problem:** A zero-length mirror response is a backend failure, not a valid prediction.

**Expected:** Empty mirror text is treated as a backend error in both router and orchestrator. Strict mode raises on empty mirror output.

**Fix:** Treat empty mirror text as a backend error in both paths.

---

---

### BUG-54: Empty tutor output is silently accepted in `run_probe_phase()` and `run_eval_phase()`

- **Severity:** High
- **Phase:** 1
- **Affected files:**
  - `xyzgl/orchestrator/tutor_phases.py` ???????? `_generate_tutor()` only treats thrown exceptions as tutor backend failure
  - `xyzgl/orchestrator/tutor_phases.py` ???????? `run_probe_phase()` and `run_eval_phase()` trust empty `res.text`
  - `xyzgl/orchestrator/parsing.py` ???????? `parse_question()` and `parse_eval_block()` turn empty text into plausible defaults

**Problem:** With `DAEDALUS_TUTOR_BACKEND=fault` and `DAEDALUS_FAULT_MODE=empty`, both `run_probe_phase()` and `run_eval_phase()` return apparently valid outputs, keep `prompt_meta.tutor_backend` on the fault backend, record no `backend_error`, and even in strict mode return normally instead of raising.

**Expected:** Empty tutor output is treated as a backend contract failure. Non-strict falls back to stub with `backend_error`; strict raises.

**Fix:** Validate `res.text` inside `_generate_tutor()` and treat empty or whitespace-only tutor output the same way exception failures are treated.

---

---

### BUG-75: Runtime tutor paths do not validate malformed backend results and crash on wrong return shapes

- **Severity:** High
- **Phase:** 1
- **Source:** `backend_probe_round14_new_issue_20260306.zip`
- **Affected files:**
  - `xyzgl/router.py`
  - `xyzgl/orchestrator/tutor_phases.py`

**Problem:** If a tutor backend returns `None` or an object missing required fields such as `.backend`, `.model`, or `.latency_ms`, runtime tutor paths crash with `AttributeError` instead of treating the malformed result as a backend contract failure. The contract probe already recognizes the same malformed returns as structured `FAIL`, so runtime and probe behavior diverge.

**Expected:** Malformed backend results are handled the same way as raised backend failures: non-strict mode records `backend_error` and falls back to stub, while strict mode raises a deliberate contract error.

**Fix:** Add a shared backend-result validator or normalizer for runtime tutor paths and validate the full return shape before dereferencing result fields.

---

---

### BUG-83: Runtime paths accept semantically invalid backend metadata values as success, so strict mode is bypassed on non-exception contract violations

- **Severity:** High
- **Phase:** 1
- **Source:** `backend_probe_round16_new_issue_20260306.zip`
- **Affected files:**
  - `xyzgl/router.py`
  - `xyzgl/orchestrator/tutor_phases.py`
  - `xyzgl/orchestrator/mirror.py`

**Problem:** The contract probe already rejects negative `latency_ms` values, but runtime paths do not revalidate backend metadata after `generate()` returns. A backend can return `BackendResult(..., latency_ms=-1)` and the runtime still treats it as success, stores impossible latency values in `tutor_meta` / `mirror_meta`, and even strict mode returns normally instead of raising.

**Expected:** Backend result metadata must satisfy the same contract in runtime paths as in the contract probe. Non-strict mode should treat invalid metadata as backend failure and degrade cleanly; strict mode should raise.

**Fix:** Add a shared runtime backend-result metadata validator and reject results when `backend` or `model` is empty/non-string or when `latency_ms` is boolean, non-integer, or negative. Use the same validation rules across router, tutor phases, and mirror runtime paths.

---

### BUG-95: Fallback error metadata is not bounded by `max_chars_out` across router and orchestrator runtime paths

- **Severity:** High
- **Phase:** 1
- **Source:** `backend_probe_round25_new_issues_20260306 (4).zip`
- **Affected files:**
  - `xyzgl/router.py`
  - `xyzgl/orchestrator/tutor_phases.py`
  - `xyzgl/orchestrator/mirror.py`

**Problem:** Non-strict fallback paths can clamp the visible reply while still preserving multi-kilobyte `backend_error` payloads in `backend_error`, `prompt_meta.backend_error`, or mirror error metadata. With exposed backend errors enabled and a large exception string, normal fallback outputs remain syntactically successful while carrying oversized error text that ignores the configured output budget.

**Expected:** Fallback error metadata is sanitized and bounded consistently with the configured output budget, so normal runtime results cannot accumulate arbitrarily large backend error payloads.

**Fix:** Clamp and sanitize all runtime fallback error surfaces (`backend_error`, phase `prompt_meta.backend_error`, mirror error metadata) to a bounded size derived from `max_chars_out` or a dedicated metadata cap.

---

### BUG-100: `run_eval_phase()` reinjects prior tutor output into the EVAL prompt as raw unescaped task text

- **Severity:** High
- **Phase:** 1
- **Source:** `grounding_injection_new_issues_round28_20260307.zip`
- **Affected file:**
  - `xyzgl/orchestrator/tutor_phases.py`

**Problem:** The EVAL prompt embeds `teach.teaching_block`, `teach.question`, and `node_title` as raw top-level prompt content ahead of the evaluation task, while `mirror_answer` and `user_answer` are structurally quoted. A compromised or injected TEACH-phase output can therefore steer the EVAL-phase model with instructions such as `IGNORE THE EVAL TASK BELOW` or forced `NEXT_ACTION: CLOSE_NODE` directives, and the requested grounding/injection suites still miss the issue because they never exercise the TEACH???EVAL orchestrator handoff.

**Expected:** Prior model output and other cross-phase text surfaces are structurally escaped or quoted before reuse in later prompts, so earlier-stage content cannot rewrite the later task.

**Fix:** JSON-quote or otherwise structurally escape `teach.teaching_block`, `teach.question`, and `node_title` before embedding them into the EVAL prompt.

---

---

### BUG-103: Backend validation and fallback tooling accept non-UTF-8-safe backend strings, so probes can PASS while artifact emission still crashes

- **Severity:** High
- **Phase:** 1 and 6
- **Source:** `backend_probe_round30_new_issues_20260307.zip`
- **Affected files:**
  - `tools/backend_contract_probe.py`
  - `tools/backend_fault_injector.py`
  - `xyzgl/router.py`
  - `witness/core.py`
  - downstream report writers such as `tools/harness_turn.py`

**Problem:** A backend can return Python `str` values containing lone surrogates or other non-UTF-8-safe content. `backend_contract_probe.py` still reports `PASS` because it only checks that `text` is a string, `backend_fault_injector.py` can still mark fallback scenarios as successful because the reply is non-empty, and the router can return a normal-looking dict that later crashes at UTF-8 write time when witness or summary artifacts are emitted.

**Expected:** Backend contract checks reject non-serializable / non-UTF-8-safe string payloads up front, fallback injectors fail such scenarios instead of green-lighting them, and runtime reply/error text is normalized or rejected before artifact emission paths run.

**Fix:** Validate backend result fields for JSON/UTF-8 writability in the contract probe and fault injector, and harden router output normalization so artifact writers do not become the first place this contract violation is detected.

---

---


## B. Session Orchestration

### BUG-07: Session loop has no terminal condition after full mastery

- **Severity:** High
- **Phase:** 3
- **Affected files:**
  - `xyzgl/orchestrator/session_loop.py` ???????? `run_session()` loops until `effective_max_turns`
  - `tools/harness_session.py` ???????? exits `0/PASS` whenever `run_session()` returns; no red path for graph completion or post-completion drift

**Problem:** After all nodes reach `confidence >= 1.0`, the session continues until the hard turn cap. The harness collapses all normal returns into `PASS`, making post-mastery drift invisible.

**Expected:** Session execution stops when no unfinished node remains. The harness distinguishes completion from overrun.

**Fix:** Add an explicit completion check in `run_session()`. Track graph-complete state in the harness and fail or flag extra post-mastery turns.

---

---

### BUG-08: Node selection ignores seed and starves tied nodes

- **Severity:** High
- **Phase:** 3
- **Affected files:**
  - `xyzgl/knowledge/heuristics.py` ???????? `select_next_node()` discards `seed` with `_ = seed`
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** Candidates sorted only by `(confidence, node_id)`. Different seeds produce the same sequence. Tied nodes are starved by lexicographic ordering.

**Expected:** Seeded runs vary selection among equally eligible nodes.

**Fix:** Use `seed` to shuffle or rotate equally scored candidates.

---

---

### BUG-09: Session orchestration loses conversational continuity across turns

- **Severity:** Medium
- **Phase:** 3
- **Affected files:**
  - `xyzgl/orchestrator/session_loop.py` ???????? `state_hint` recomputed; PROBE turns hardcode `user_state="frustrated"`
  - `xyzgl/orchestrator/tutor_phases.py` ???????? `run_probe_phase()` loses the pointed question

**Problem:** New-node selection ignores inferred learner state. PROBE turns always pass `"frustrated"`. Pointed question lost if tutor output is generic.

**Expected:** Latest `user_state` carries across transitions and probes.

**Fix:** Persist `session_user_state` inside `run_session()`. In `run_probe_phase()`, prefer the normalized pointed question.

---

---

### BUG-85: `session_report.json` can serialize an impossible follow-up question on `CLOSE_NODE` turns

- **Severity:** Medium
- **Phase:** 4
- **Source:** `xyzgl_new_issues_report_round17.md`
- **Affected files:**
  - `tools/harness_session.py`
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** The exported session artifact can record `eval.next_action = "CLOSE_NODE"` while still serializing a non-empty `eval.next_question` such as `Q2: What's the missing step in your reasoning?`. That encodes an impossible next step on turns that have already closed and makes the bundle semantically inconsistent.

**Expected:** Close-node turns serialize terminal evaluation state only. If a node is already closed, `next_question` should be absent, null, or moved to a separate non-authoritative debug field.

**Fix:** Clear or suppress `eval.next_question` whenever `next_action` is `CLOSE_NODE`, and ensure artifact serialization reflects the terminal action that actually won.

---

---


## C. Single-Turn Harness & Artifacts

### BUG-10: `harness_turn` crashes on failure / lone-surrogate Unicode and leaves empty run dirs

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/harness_turn.py` ???????? `run_dir` allocated before `route_turn()`; no `try/except`
  - `witness/core.py` ???????? serializer writes JSON with `ensure_ascii=False`; lone-surrogate text raises `UnicodeEncodeError`

**Problem:** If `route_turn()` raises, the script exits without writing artifacts. Lone-surrogate Unicode crashes the witness serializer.

**Expected:** A deterministic failure bundle is always written. Invalid Unicode is safely replaced.

**Fix:** Wrap `route_turn()` in `try/except` and always emit artifacts. Sanitize invalid Unicode before serialization.

---

---

### BUG-11: `harness_turn` leaks sensitive input into artifacts

- **Severity:** High
- **Phase:** 4
- **Affected file:**
  - `tools/harness_turn.py` ???????? `_artifact_result()` only truncates, does not sanitize; summary writes `args.text` directly

**Problem:** User-supplied secrets and PII written into witness reports and markdown summaries.

**Expected:** Artifact payloads and summaries are sanitized before writing.

**Fix:** Sanitize with `_sanitize_obj()` and `_sanitize_text()`.

---

---

### BUG-23: Turn artifacts do not faithfully record the model-facing input

- **Severity:** High
- **Phase:** 4
- **Affected files:**
  - `tools/harness_turn.py` ???????? summary writes raw `args.text`; report records normalized `text_in`
  - `xyzgl/router.py` ???????? `text_in` is normalized but not the final prompt-facing user block
  - `xyzgl/prompting.py` ???????? separately sanitizes marker tokens before interpolation

**Problem:** For whitespace-normalized or marker-bearing inputs, the artifacts do not match what the tutor backend actually saw.

**Expected:** Turn artifacts clearly distinguish raw CLI input, normalized routed input, and the final prompt-facing user block.

**Fix:** Store the canonical routed input and the final prompt-facing sanitized user segment explicitly.

---

---

### BUG-24: `turn_summary.md` is artifact-unsafe and uncapped

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_turn.py` ???????? `_md_fenced()` HTML-escapes content inside fenced code blocks; no size cap

**Problem:** Fenced code blocks stop being faithful when `<`, `>`, `&` are escaped. Raw NUL bytes can turn the markdown into a binary file. Very large inputs produce uncapped summaries.

**Expected:** Fenced blocks are faithful, control characters are stripped, and summary size is bounded.

**Fix:** Stop HTML-escaping fenced blocks. Strip control characters. Apply the same size policy as JSON bundles.

---

---

### BUG-37: `harness_turn` hides mirror-path output from the human-readable summary

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_turn.py` ???????? JSON artifact contains `mirror_prediction` and `mirror_meta` but markdown summary only renders input and tutor reply

**Problem:** Mirror-enabled runs are flattened into tutor-only summaries.

**Expected:** Summary includes mirror prediction and metadata when present.

**Fix:** Render mirror output in the summary when `mirror_prediction` or `mirror_meta` are populated.

---

---

### BUG-49: `harness_turn.py` treats an empty tutor reply as a clean PASS

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_turn.py` ???????? accepts and serializes `turn_result.reply = ""` with no failure condition

**Problem:** With `DAEDALUS_TUTOR_BACKEND=fault` and `DAEDALUS_FAULT_MODE=empty`, the tool exits `0`, writes a normal `turn_report.json`, records no `backend_error`, and renders a blank reply block.

**Expected:** A zero-length tutor reply is treated as a backend contract failure.

**Fix:** Assert that the tutor reply is non-empty after `route_turn()`. If empty, emit a structured FAIL artifact.

---

---

### BUG-86: `harness_turn.py` can emit unstable `event_id` values for semantically identical deterministic runs

- **Severity:** Medium
- **Phase:** 4
- **Source:** `xyzgl_turn_fresh_issues_report_18.md`
- **Affected files:**
  - `tools/harness_turn.py`
  - `witness/core.py`

**Problem:** Re-running the same issue/seed/text against the deterministic fault `slow` path can produce the same reply but different `turn_report.json.event_id` values because `WitnessCore._event_id()` hashes payload fields that include jittering `tutor_meta.latency_ms`. The same bundle lineage can therefore claim `deterministic: true` in `run.json` while still changing witness identity across identical logical runs.

**Expected:** Deterministic artifact identity is derived from semantically stable turn content, not from volatile timing measurements. If timing jitter is intentionally retained, the run should not be labeled deterministic.

**Fix:** Exclude volatile telemetry such as observed latency from the event-id hash input, or split deterministic witness identity from non-deterministic timing metadata.

---

---

### BUG-87: `property_turn_fuzzer.py` bypasses backend-error redaction and can leak raw exception text into artifacts

- **Severity:** High
- **Phase:** 6
- **Source:** `xyzgl_turn_fresh_issues_report_18.md`
- **Affected files:**
  - `tools/property_turn_fuzzer.py`
  - `xyzgl/backends/fault.py`

**Problem:** When `route_turn()` raises, the fuzzer catches the Python exception and serializes `str(e)` directly into `property_fuzz_report.json` (`problems[]` and `results[*].exception`) even when `DAEDALUS_EXPOSE_BACKEND_ERRORS=0`. Because the fault backend echoes invalid mode strings in exception text, secret-looking values can be written into artifacts verbatim through this path.

**Expected:** Tool artifacts honor the same backend-error exposure and redaction policy as the runtime path. Raw exception strings, especially secret-like values, are sanitized before persistence.

**Fix:** Route caught exception text through the shared backend-error redaction/sanitization policy, store structured failure classes instead of raw exception strings, and scrub both summary and per-result exception fields before writing artifacts.

---

---


## D. Session Harness & Sweep Stability

### BUG-12: Session harness does not exercise PROBE and simulated learner ignores context

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_session.py` ???????? `_simulated_user_answer()` always includes all required keywords; ignores question text

**Problem:** Harness closes nodes too quickly; never triggers a real PROBE cycle. Repeated visits produce byte-identical answers.

**Expected:** First answers are intentionally incomplete. Simulated answers vary based on question content and prior attempts.

**Fix:** Track per-node attempt counts. Omit keywords on attempt zero. Feed question text and history into `_simulated_user_answer()`.

---

---

### BUG-13: Session/sweep artifacts are not byte-stable; seed_sweep is a false proxy with masked failures

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/harness_session.py` / `tools/run_paths.py` ???????? timestamp-based run IDs
  - `witness/core.py` ???????? wall-clock `created_at`
  - `tools/seed_sweep.py` ???????? calls `route_turn()` not `run_session()`; default run IDs are time-based

**Problem:** Identical invocations produce different artifact bytes. Seed sweep exercises single turns, not the session loop. Backend fallback and mirror failures are hidden. All-empty reply sweeps report PASS. Raw input recording and Unicode normalization create false drift. Crashes leave orphan empty run directories.

**Expected:** Deterministic harnesses use stable IDs. Seed sweep validates live session behavior. Backend fallback, mirror failure, and empty replies are surfaced.

**Fix:** Derive run IDs from hashed inputs. Rework sweep to cover `run_session()`. Surface backend provenance and mirror errors. Add non-empty reply invariant. Record canonical routed input.

---

---

### BUG-32: `harness_session` ignores env-backed protocol reground cadence

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_session.py` ???????? builds config with `XYZGLConfig()` instead of `XYZGLConfig.from_env()`

**Problem:** `DAEDALUS_PROTOCOL_REGROUND_EVERY=1` does not change the actual reground cadence.

**Expected:** Env-backed config values are respected by the session harness.

**Fix:** Use `XYZGLConfig.from_env()` as the base config, then overlay CLI-specified fields.

---

---

### BUG-33: `harness_session` ignores env-backed protocol and grounding paths

- **Severity:** Medium
- **Phase:** 4
- **Affected file:**
  - `tools/harness_session.py` ???????? hardcodes config fields instead of reading from env

**Problem:** `DAEDALUS_PROTOCOL_PATH` and `DAEDALUS_GROUNDING_DIR` are ignored.

**Expected:** Env-backed protocol and grounding paths are respected.

**Fix:** Same root cause as BUG-32 ???????? use `XYZGLConfig.from_env()` as the base config.

---

---

### BUG-43: `GWEN_DISABLED=1` is a dead isolation switch in harness paths

- **Severity:** High
- **Phase:** 4
- **Affected files:**
  - `tools/harness_turn.py` ???????? patches env with `GWEN_DISABLED=1`
  - `tools/harness_session.py` ???????? same dead env patch

**Problem:** The runtime tree does not read `GWEN_DISABLED`. Mirror-related behavior can still execute or fault even when the harness believes it has disabled that subsystem.

**Expected:** Either the runtime honors `GWEN_DISABLED`, or the harnesses stop setting a flag that nothing consumes.

**Fix:** Replace the dead env toggle with an actual config override.

---

---

### BUG-50: Mirror enablement and privacy controls are not propagated or auditable across session tooling

- **Severity:** High
- **Phase:** 4
- **Affected files:**
  - `tools/harness_session.py` ???????? ignores `DAEDALUS_ENABLE_MIRROR=1` unless `--enable-mirror` is passed
  - `xyzgl/orchestrator/mirror.py` ???????? session path does not consult `DAEDALUS_MIRROR_SEND_USER_CONTENT`
  - `tools/seed_sweep.py` ???????? saved artifacts drop the mirror privacy-state difference

**Problem:** Mirror enablement from environment alone does not take effect in the session harness. The session mirror path does not vary or record raw-vs-redacted prompt mode.

**Expected:** Env-backed mirror enablement is honored. `DAEDALUS_MIRROR_SEND_USER_CONTENT` changes session mirror behavior. Artifacts record `prompt_mode`.

**Fix:** Base harness config on `XYZGLConfig.from_env()`. Thread mirror privacy mode through session artifacts.

---

---

### BUG-51: `backend_contract_probe.py` accepts spoofed backend identity metadata as PASS

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/backend_contract_probe.py` ???????? `_probe_one()` validates types but does not verify that `res.backend` matches the backend under test and does not require a non-empty `model`

**Problem:** The contract probe will PASS results such as `backend='spoofed-backend', model=''` while probing the stock stub backends. This makes the probe too weak to catch backend provenance regressions.

**Expected:** Probe results fail when the reported backend label does not match the backend being probed. Empty or whitespace-only model strings should also fail.

**Fix:** Map each requested backend token to allowed labels, reject mismatches, and require non-empty `model.strip()` for PASS.

---

---

### BUG-52: `seed_sweep.py` run identity is predictably tied to `--seed`, not to the actual sweep workload

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/seed_sweep.py` ???????? auto-generated run-id suffix stable for configured seed
  - `tools/run_paths.py` ???????? collision suffixing can allocate different on-disk dir while artifacts retain pre-collision `run_id`

**Problem:** Real runs with the same seed reuse the same 4-digit suffix even when issue ID, seed range, and input text differ. The top-level `seed` field in `seed_sweep_report.json` is tied to run-id generation, not to the tested sweep workload.

**Expected:** Artifact identity should be workload-derived or freshly unique per run. Every artifact records the actual final allocated run identity.

**Fix:** Stop deriving run-id suffix from `--seed`. Generate from fresh entropy or workload hash. Propagate final allocated identity into every artifact.

---

---

### BUG-55: `run_paths.py` resolves default and relative runs roots against the caller's current working directory

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/run_paths.py` ???????? default runs root and relative `DAEDALUS_RUNS_DIR` resolution are CWD-dependent
  - `tools/harness_session.py` ???????? writes bundles under `tools/runs/` when launched from `tools/`
  - `tools/seed_sweep.py` ???????? same unstable run-root behavior

**Problem:** Launching the same tool from the repo root versus from `tools/` changes the artifact destination. Default runs can land in `tools/runs/` instead of repo-root `runs/`.

**Expected:** Default run output locations are anchored to the repository, not the shell's CWD.

**Fix:** Resolve the default runs root from repository-local code location. Normalize relative `DAEDALUS_RUNS_DIR` against the repo root.

---

---

### BUG-60: Invalid `DAEDALUS_RUNS_DIR` overrides are silently ignored

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/run_paths.py:36-59`
  - `tools/harness_turn.py:97-98`
  - `tools/property_turn_fuzzer.py:156-157`

**Problem:** `runs_root()` uses `DAEDALUS_RUNS_DIR` only if `_is_writable_dir()` succeeds. If the override points at a non-directory or unwritable path, the code silently falls back to `cwd/runs` or a temp directory. Tools then allocate a bundle in the fallback location and still exit `PASS`.

**Expected:** An invalid explicit override is treated as `INCOMPLETE`, or at minimum the rejection and actual output root are recorded in the emitted bundle.

**Fix:** Treat invalid explicit overrides as `INCOMPLETE`, or record the rejection and the actual output root.

---

---

### BUG-62: `harness_turn.py` artifacts are not self-describing for env-only backend-error exposure and fault-injection runs

- **Severity:** Medium
- **Phase:** 4
- **Affected files:**
  - `tools/harness_turn.py:103-130`
  - `xyzgl/router.py:146-148, 250-277`
  - `xyzgl/backends/fault.py:68-92`

**Problem:** `route_turn()` exposes or redacts `backend_error` based on `DAEDALUS_EXPOSE_BACKEND_ERRORS`, which is not part of `XYZGLConfig`. Two bundles can differ materially while claiming the same saved config. Additionally, fault backend behavior depends on `DAEDALUS_FAULT_MODE` and `DAEDALUS_FAULT_DELAY_MS`, which are not preserved in the artifact.

**Expected:** Env-only behavior switches and fault-relevant execution knobs are captured in the artifact.

**Fix:** Persist the effective backend-error exposure mode and fault settings in bundle metadata, or move those controls into `XYZGLConfig`.

---

---

### BUG-82: Session artifacts misreport the learner state that actually drove tutoring, and the `flow` vs `frustrated` stub-tutor branch is behaviorally dead in exported output

- **Severity:** Medium
- **Phase:** 3
- **Source:** `xyzgl_new_issues_report_round15.md`
- **Affected files:**
  - `tools/harness_session.py`
  - `xyzgl/orchestrator/session_loop.py`

**Problem:** Once the session reaches flow turns, the saved artifact can label a turn with the post-answer inferred `user_state` instead of the `teach.user_state` that actually drove tutor generation for that turn. In the same evidence, turns that used materially different in-memory tutoring states (`frustrated` with light budget versus `flow` with dense budget) still emit byte-identical question and teaching text on the stub tutor path. That makes the exported bundle semantically misleading and makes the state branch effectively untestable from artifacts.

**Expected:** Session artifacts should clearly distinguish the tutoring-time learner state from any later inferred post-answer state. When a different learner-state branch is taken, either the tutoring behavior or the serialized artifact should expose that distinction in a stable, reviewable way.

**Fix:** Persist both the tutor-driving state and the post-eval inferred state in the session artifact. Ensure the exported turn data and summaries reflect the state that actually drove teaching. If the stub tutor intentionally ignores the state branch, surface that explicitly in metadata or revise the branching logic so the state change becomes externally observable and testable.

---

---

### BUG-84: Session harness exports do not preserve the evidence needed to audit learner-state inference and deterministic node closure

- **Severity:** Medium
- **Phase:** 4
- **Source:** `xyzgl_new_issues_report_round16.md`
- **Affected files:**
  - `tools/harness_session.py`
  - `xyzgl/orchestrator/session_loop.py`
  - `xyzgl/orchestrator/policies.py`

**Problem:** The default harness fixture hardcodes short simulated answers and fixed `typing_ms = 4500`, so the default graph self-closes immediately while the `flow` and slow-typing learner-state branches remain unreachable in ordinary runs. At the same time, exported `session_report.json` turn records omit the telemetry and deterministic close-gate evidence that actually drove those transitions. Reviewers therefore cannot tell from the artifact why a turn stayed `frustrated`, why a node closed, or whether the harness ever exercised the intended state branches.

**Expected:** Harness fixtures should cover both closure and non-closure paths, vary answer length and typing latency enough to exercise the state-inference branches, and serialize the telemetry plus deterministic close-gate evidence needed to audit each transition.

**Fix:** Update the default harness simulator to produce intentionally incomplete first answers, vary answer length across turns, and surface slow-typing cases. Persist per-turn telemetry, `required_keywords`, and the close-gate result (or equivalent deterministic closure evidence) in the exported session artifact.

---

### BUG-101: Multiple standalone tools accept semantically invalid CLI parameters and then coerce, crash, or emit internally inconsistent artifacts

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_16th_pass_2026-03-07.md`
- **Affected files:**
  - `tools/seed_sweep.py`
  - `tools/atheris_fuzz_router.py`
  - `tools/mirror_calibration_bench.py`
  - `tools/mutation_suite.py`

**Problem:** Several tools preserve invalid CLI inputs in their artifacts while executing different semantics or crashing late. `seed_sweep.py` accepts `--turn-index -1` and still reports `PASS`; `atheris_fuzz_router.py` accepts non-positive `--seconds` values and silently coerces them into a normal positive workload; `mirror_calibration_bench.py` accepts `--min-avg inf`, crashes during JSON serialization, and leaves an empty orphan run dir; `mutation_suite.py --engine builtin --target nope --dry-run` reports `INCOMPLETE` yet still emits builtin `xyzgl` mutants. These are semantic input-validation failures, not mere user mistakes, because the produced artifacts no longer describe the executed or valid contract state faithfully.

**Expected:** Invalid numeric, non-finite, or unsupported CLI arguments are rejected up front before run-dir allocation or report emission, and no tool emits target-specific or success-like payloads for an invalid configuration.

**Fix:** Validate semantic ranges, finite floats, and supported targets before execution begins, and suppress contradictory artifact payloads when the requested configuration is invalid.

---


## E. Replay Diff Tool

### BUG-14: `repro_replay_diff` reconstructs session input differently from harness

- **Severity:** High
- **Phase:** 5
- **Affected files:**
  - `tools/repro_replay_diff.py` ???????? only inspects first line, only recognizes `NODE:`
  - `tools/harness_session.py` ???????? parses first few lines, prefers `NODE_ID:`

**Problem:** Replay uses different parsing than the producing harness. Real prompts begin with `NODE_ID:`, so replay falls to `node_id="unknown"`. Current reproduction confirms the failure still occurs on standard internal runs.

**Expected:** Replay uses the same prompt-to-node reconstruction logic.

**Fix:** Port parsing logic from `harness_session.py`. Parse `NODE_ID:` first, then fall back to `NODE:`.

---

---

### BUG-15: `repro_replay_diff` masks session failures in mixed directories

- **Severity:** High
- **Phase:** 5
- **Affected file:**
  - `tools/repro_replay_diff.py` ???????? `elif` branch skips `session_report.json` if a passing `turn_report.json` exists

**Problem:** Replay-failing session becomes `PASS` when placed beside a passing turn report.

**Expected:** Both artifacts checked; any failure makes the result fail.

**Fix:** Remove turn-vs-session precedence. Scan both and aggregate all problems.

---

---

### BUG-16: `repro_replay_diff` ignores turn-level mirror, fallback, and backend provenance drift

- **Severity:** Medium
- **Phase:** 5
- **Affected file:**
  - `tools/repro_replay_diff.py` ???????? turn comparison covers only `reply`, `backend`, `prompt_meta`, and `config`; even `--strict` does not compare full provenance

**Problem:** A replay can drift materially in mirror content, fallback paths, or backend routing provenance while the diff tool reports no meaningful difference.

**Expected:** Turn comparison includes mirror outputs, backend error/fallback state, and provenance fields.

**Fix:** Extend turn comparison keys. Add backend provenance fields to strict comparisons.

---

---

### BUG-31: `targeted_sweep.py` does not forward `--allow-external-path` to child tools

- **Severity:** Medium
- **Phase:** 5
- **Affected files:**
  - `tools/targeted_sweep.py` ???????? invokes path-gated tools without `--allow-external-path`
  - `tools/run_paths.py` ???????? allows external run roots

**Problem:** On valid external run roots, the sweep creates healthy artifacts but marks downstream verification steps `INCOMPLETE`.

**Expected:** Sweep succeeds or fails based on artifact content, not missing external-path flags.

**Fix:** Detect when child run dir is external and forward `--allow-external-path`.

---

---

### BUG-45: `targeted_sweep.py` sanitizes child output before extracting run paths

- **Severity:** Medium
- **Phase:** 5
- **Affected file:**
  - `tools/targeted_sweep.py` ???????? `_step()` sanitizes absolute paths before returning; `_extract_path()` cannot recover the emitted run directory

**Problem:** `sess_dir` / `sess2_dir` can become `None` even when the child harness succeeded. Downstream checks are silently skipped.

**Expected:** Internal parsing uses raw child output. Human-facing reports keep the sanitized version.

**Fix:** Return both raw and sanitized stdout tails from `_step()`, parse from the raw form, persist only the sanitized form.

---

---

### BUG-65: `repro_replay_diff.py` ignores sibling `turn_summary.md` input drift

- **Severity:** High
- **Phase:** 5
- **Affected file:**
  - `tools/repro_replay_diff.py:261-288`

**Problem:** In the turn-bundle path, the tool extracts `payload.turn_result` and replays only from that JSON payload. It never reads or cross-checks `turn_summary.md`. A bundle can become internally inconsistent after tampering and still pass replay diff.

**Expected:** The turn bundle is treated as a multi-file artifact and `turn_summary.md` input text is cross-checked.

**Fix:** Cross-check `turn_summary.md` input text against `payload.turn_result.input` when the summary is present.

---

---

### BUG-67: `targeted_sweep.py` contaminates the repo before running `doctor`

- **Severity:** High
- **Phase:** 5
- **Affected files:**
  - `tools/targeted_sweep.py:126-130, 154-160, 219-234`
  - `tools/doctor.py:157-168, 197-202`

**Problem:** The sweep allocates its own `run_dir` through the normal repo-local runs path and creates artifacts before or during the `doctor` step. `doctor.py` treats any non-empty repo `runs/` directory as contamination and returns `INCOMPLETE`. The sweep causes `doctor` to fail because of its own artifacts.

**Expected:** The sweep does not self-contaminate the `doctor` check.

**Fix:** Force the sweep's own bundle outside the repo tree, or give `doctor` an isolated runs root that excludes sweep artifacts.

---

---

### BUG-72: `repro_replay_diff.py` ignores sibling `knowledge_graph.json` drift in session bundles

- **Severity:** Medium
- **Phase:** 5
- **Affected file:**
  - `tools/repro_replay_diff.py:290-303`

**Problem:** The session replay path compares only the replayed `turns` payload hash. It does not compare the sibling `knowledge_graph.json` artifact. Session behavior can drift in graph state even when the turn transcript stays stable.

**Expected:** Replay comparison includes the graph artifact or explicitly reports that graph drift is out of scope.

**Fix:** Compare the sibling graph export as part of session replay, or surface a warning when a graph artifact is ignored.

---

---

### BUG-74: `repro_replay_diff.py` ignores sibling `session_summary.md` drift in session bundles

- **Severity:** Medium
- **Phase:** 5
- **Source:** `behavior_drift_replay_bundle_round13.zip` finding 1
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** The tool can still return `PASS` when `session_summary.md` is mutated so the summarized tutor question no longer matches `session_report.json`. It compares replayed turn hashes only and never reads the sibling summary artifact, so summary-only drift is invisible.

**Expected:** Session replay validation checks the human-facing summary artifact when it exists, or explicitly declares it out of scope instead of silently ignoring summary drift.

**Fix:** Parse `session_summary.md` alongside `session_report.json` in directory mode and fail when canonical summary fields such as tutor question, node, or user answer drift from the witness payload.

---

---

### BUG-90: `repro_replay_diff.py` ignores cross-file `run.json.issue_id` drift in turn bundles

- **Severity:** Medium
- **Phase:** 5
- **Source:** `behavior_drift_replay_bundle_round19.zip`
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** Replay diff can return `PASS` for a turn bundle whose sibling `run.json.issue_id` contradicts the issue metadata carried by `turn_report.json` and `turn_summary.md`. The tool replays only from the witness artifact payload and never cross-checks the sibling bundle metadata, so a cross-file integrity drift is invisible.

**Expected:** Replay integrity checks treat the turn bundle as a multi-file artifact and fail when `run.json.issue_id` does not match the witness artifact issue metadata.

**Fix:** Cross-check sibling `run.json` metadata against the replayed artifact before reporting a clean replay result.

---

---

### BUG-104: `repro_replay_diff.py` ignores inner `payload.session_report.schema_version` drift in session bundles

- **Severity:** Medium
- **Phase:** 5
- **Source:** `behavior_drift_replay_bundle_round26.zip`
- **Affected file:**
  - `tools/repro_replay_diff.py`

**Problem:** In the session replay branch, the tool compares only the `turns` payload hash and never checks whether the stored inner `payload.session_report.schema_version` still matches the replayed canonical value. A crafted session bundle can therefore mutate the recorded session schema version and still receive a clean `PASS` as long as the turn list hashes match.

**Expected:** Replay integrity checks treat the inner `session_report` schema version as part of the validated artifact contract and fail when the stored inner value drifts from the replayed session payload.

**Fix:** Compare the recorded `payload.session_report.schema_version` against the replayed session schema version in the session branch and fail on mismatch.

---

---


## F. Detection & Quality Gates

### BUG-17: Mirror/drift detection tools are too narrow and fragile

- **Severity:** High
- **Phase:** 6
- **Affected files:**
  - `tools/mirror_leakage_detector.py` ???????? narrow phrase list misses numbered steps, imperative starters, first-person procedural advice, explicit tutor-role claims (`As your tutor`), and lesson framing (`In today's lesson`); does not normalize zero-width separators or markup; can crash on non-string `mirror.answer`
  - `tools/protocol_drift_radar.py` ???????? narrow marker list; mirror role confusion emitted as `WARN`

**Problem:** Leakage regexes miss broad categories of tutor-style language including imperative constructions (`Need to keep the arc short`), tutor self-labeling, and lesson framing. Simple presentation tricks bypass known triggers. Non-string payloads crash the tool. Mirror answers in eval/session data are not scanned. Mirror role confusion is graded `WARN` instead of failing.

**Expected:** Both detectors flag obvious tutor-style language after normalization. Mirror role confusion escalates to `HIGH`. Non-string payloads produce safe failures. Mirror answers in eval/session data are scanned.

**Fix:** Normalize zero-width characters and markup before scanning. Expand patterns to include imperative starters, instructional scaffolding, role claims, lesson framing, and first-person procedural advice. Type-check `mirror.answer`. Promote mirror role confusion to `HIGH`. Scan mirror answers in eval/session data.

---

---

### BUG-18: Graph invariant checker fail-opens on malformed input

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/graph_invariant_checker.py`

**Problem:** (1) `_load_json()` calls `time.sleep()` without importing `time`. (2) Parse exceptions fall to `kg = {}` and validation continues. (3) `overall =` overwrites `INCOMPLETE`. (4) Root-level unexpected properties not rejected. (5) Non-string `required_keywords` only fail under `--strict`. (6) `bool` passes `int()` checks for `last_verified_turn`. (7) Missing `summary` field not enforced. (8) `fragility_flags` item types not validated. (9) Numeric strings pass `float()` coercion. (10) No size/budget checks for node titles, summaries, keyword counts, keyword lengths, or graph-core limits (max node count, max token width, max flags per node). (11) Overlong `node_id` values that collide after graph-core truncation are not detected.

**Expected:** Malformed JSON returns `INCOMPLETE`. Schema violations, wrong types, boolean-for-integer, missing required fields, stringified numerics, and graph-core boundedness violations all fail by default.

**Fix:** Import `time` or remove retry sleep. Stop validation after parse failure. Enforce `summary`, `fragility_flags` types, reject stringified numerics. Add graph-core size/budget checks and normalized-ID collision detection.

---

---

### BUG-22: Quality gates (selfcheck + mutation suite) are stale

- **Severity:** Medium
- **Phase:** 6
- **Affected files:**
  - `tools/selfcheck.py` ???????? only checks input roundtrip and non-empty reply
  - `tools/mutation_suite.py` ???????? two builtin patterns no longer match current router source

**Problem:** CI green on low-signal checks while critical behavior regresses. Mutation patterns disconnected from actual code. Current evidence confirms `MUT-001` and `MUT-002` still fail with `mutation pattern not found`.

**Expected:** Selfcheck asserts core router invariants. Mutation patterns match current code.

**Fix:** Expand selfcheck coverage. Refresh builtin mutation patterns.

---

---

### BUG-25: `property_turn_fuzzer.py` under-validates failures and omits failing payloads

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/property_turn_fuzzer.py` ???????? `_check_shape()` ignores `backend_error`, consistency of `requested_backend`/`effective_backend`; failure rows do not store testcase text

**Problem:** A deterministic fallback regression can still show `PASS` if reply shape looks valid. The shape checker does not fail on empty-string replies, populated `backend_error`, or degraded-path metadata. The fuzzer report collapses materially different backend behaviors into the same coarse shape. Missing input payload makes reproduction harder.

**Expected:** Fuzzer fails on backend provenance regressions, empty replies, and unexpected failure markers. Preserves failing testcase inputs. Reports enough signal to distinguish different backend paths.

**Fix:** Extend `_check_shape()`. Persist reply excerpts/hashes, backend metadata, and fault configuration alongside pass/fail. Persist sanitized testcase input for every failing row.

---

---

### BUG-26: `protocol_drift_radar.py` has a tail-position blind spot after 4,000 characters

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/protocol_drift_radar.py` ???????? `_clip_text()` truncates to first 4,000 characters only

**Problem:** Mirror drift phrases near the end of a long reply are dropped before regex scanning.

**Expected:** Scanning catches phrases regardless of text position.

**Fix:** Preserve both head and tail when clipping, or scan the full text in bounded windows.

---

---

### BUG-29: `backend_contract_probe.py` accepts empty backend output as PASS

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/backend_contract_probe.py` ???????? `_probe_one()` verifies `text` is a string but never requires non-empty

**Problem:** Zero-length output violates the contract. CI can mark a silent empty-output backend as healthy.

**Expected:** Probe requires `text.strip()` to be non-empty for PASS.

**Fix:** Require non-empty text for successful probe results.

---

---

### BUG-30: `backend_fault_injector.py` has a false-positive hole and omits key fault scenarios

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/backend_fault_injector.py` ???????? `_scenario()` only requires no exception plus `reply_nonempty`; stock scenarios omit mirror-empty and tutor-empty

**Problem:** Regressions in backend error recording and fallback behavior still show PASS. `effective_backend` switch is never asserted.

**Expected:** Assertions verify fallback/error invariants. Both mirror-empty and tutor-empty scenarios are in the stock matrix.

**Fix:** Strengthen scenario assertions. Add mirror-empty and tutor-empty scenarios.

---

---

### BUG-34: `property_turn_fuzzer.py` writes non-canonical `run.json`

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/property_turn_fuzzer.py` ???????? `_write_bundle()` uses raw `json.dumps()` instead of canonical writer

**Problem:** `run.json` is not stable under canonical reserialization, breaking byte-stable comparisons.

**Expected:** All tool-produced `run.json` files use the canonical JSON writer.

**Fix:** Replace raw `json.dumps()` with the canonical writer.

---

---

### BUG-35: Turn fuzzer cannot reach the welding-specific single-turn branch

- **Severity:** Medium
- **Phase:** 6
- **Affected files:**
  - `tools/property_turn_fuzzer.py` ???????? fuzz alphabet cannot spell trigger words
  - `xyzgl/router.py` ???????? welding-specific branch

**Problem:** The fuzz alphabet cannot produce trigger words (`tack`, `gap`, `uneven`). In a 5,000-case repro the branch was never reached.

**Expected:** The fuzzer's vocabulary can reach all deterministic code branches.

**Fix:** Include known branch-trigger vocabulary in the fuzz alphabet.

---

---

### BUG-36: Turn fuzzer cannot generate known control and Unicode stressors

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/property_turn_fuzzer.py` ???????? generator alphabet omits NUL, CR, ESC, lone surrogates, combining marks

**Problem:** The fuzzer cannot rediscover deterministic bugs that depend on these character classes.

**Expected:** The fuzz generator can produce all known stressor character classes.

**Fix:** Extend the generator alphabet.

---

---

### BUG-38: `prompt_snapshot_guard.py` silently rewrites baseline without `--update`

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/prompt_snapshot_guard.py` ???????? logic equivalent to `if args.update or not baseline:` causes self-seeding

**Problem:** Missing baseline is recreated and returns `PASS` even without `--update`.

**Expected:** Without `--update`, a missing baseline produces `FAIL` or `INCOMPLETE`.

**Fix:** Only create/update the baseline when `--update` is explicitly passed.

---

---

### BUG-39: `backend_contract_probe` falsely fails the supported `slow` fault mode

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/backend_contract_probe.py` ???????? `expected_raise` derived from backend name alone

**Problem:** Supported non-raising fault modes such as `slow` are misclassified as failures.

**Expected:** Probe distinguishes between raising and non-raising fault modes.

**Fix:** Derive `expected_raise` from the actual fault mode, not the backend name.

---

---

### BUG-40: Multiple tools accept malformed `--issue` IDs and emit schema-invalid bundles

- **Severity:** Medium
- **Phase:** 6
- **Affected files:**
  - `tools/latency_cost_budget_enforcer.py`, `tools/grounding_injection_audit.py`, `tools/repro_grounding_protocol_smoke.py`, `tools/curriculum_corpus_linter.py`, `tools/backend_fault_injector.py`, `tools/repro_backends_smoke.py`, and ~10 others

**Problem:** Tools accept values like `NOT-AN-ISSUE` and write artifacts whose `issue_id` violates the schema pattern.

**Expected:** Every issue-scoped tool rejects invalid `ISSUE-YYYYMMDD-NNN` values up front.

**Fix:** Apply `validate_issue_id()` in every tool that emits an issue-scoped bundle.

---

---

### BUG-41: `latency_cost_budget_enforcer.py` is not hermetic

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/latency_cost_budget_enforcer.py` ???????? builds `cfg = XYZGLConfig.from_env()`

**Problem:** Ambient backend env can turn a local latency budget check into an uncaught backend config/runtime failure.

**Expected:** The tool runs under a cleared or explicitly stubbed backend config.

**Fix:** Clear backend-related env vars or construct an explicit stub-only config.

---

---

### BUG-42: `grounding_injection_audit.py` is environment-sensitive and can misattribute failures

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/grounding_injection_audit.py` ???????? starts from `XYZGLConfig.from_env()`, copies `grounding_dir`; silently falls back to `curriculum`

**Problem:** Ambient `DAEDALUS_GROUNDING_DIR` can change the tool result. The tool records the env-provided directory while silently falling back to the repo curriculum path.

**Expected:** The audit uses one sanitized grounding source consistently.

**Fix:** Normalize and validate the grounding directory before constructing the config.

---

---

### BUG-44: `property_turn_fuzzer.py` truncates evidence and changes schema on incomplete path

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/property_turn_fuzzer.py` ???????? Hypothesis-missing branch writes different schema; normal report truncates `problems` to 50 with no counter

**Problem:** The incomplete path produces a schema-incompatible report. Truncated evidence has no dropped-count indicator.

**Expected:** All exit paths emit one stable report schema and explicitly record dropped evidence counts.

**Fix:** Keep one report schema across all paths. Add `problems_dropped` counter.

---

---

### BUG-53: `tools/signal_fidelity_port.py` is missing required companion docs

- **Severity:** Medium
- **Phase:** 6
- **Affected files:**
  - `tools/signal_fidelity_port.py`
  - Missing expected docs: `documentation/tools/ai_signal_fidelity_port.md` and `documentation/tools/ai_signal_fidelity_port.txt`

**Problem:** `tools/doc_code_link_checker.py --enforce` reports missing tool docs for `signal_fidelity_port`. The repository policy requires matching tool docs under `documentation/tools/ai_<tool>.md|.txt`, so the tool currently fails the enforced documentation gate.

**Expected:** Every shipped tool has the required companion documentation files.

**Fix:** Add the missing docs or adjust the tool registration/policy if the tool is intentionally excluded.

---

---

### BUG-56: `backend_contract_probe.py` can report PASS without probing any backend

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/backend_contract_probe.py:136-170`

**Problem:** Backend lists are built from `args.tutor_backends` and `args.mirror_backends`. If both lists end up empty, no probes run. `overall` starts as `"PASS"` and remains `"PASS"` because `status_set` stays empty. The tool can emit a green contract report with `"results": []`.

**Expected:** Empty backend selection is rejected up front. Zero-probe runs return `INCOMPLETE` or `FAIL`.

**Fix:** Reject empty backend selection up front and return `INCOMPLETE` or `FAIL` instead of allowing a zero-probe pass.

---

---

### BUG-57: `backend_contract_probe.py` accepts boolean `latency_ms` values as valid integers

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/backend_contract_probe.py:88-116`

**Problem:** The contract check uses `isinstance(latency_ms, int)`. In Python, `bool` is a subclass of `int`, so `True` and `False` satisfy the type gate. The tool can green-light malformed latency metadata.

**Expected:** Reject `bool` explicitly before accepting `latency_ms` as an integer.

**Fix:** Add `not isinstance(latency_ms, bool)` check.

---

---

### BUG-59: `retrieval_eval_bench.py` accepts symlink corpora that runtime grounding rejects

- **Severity:** Medium
- **Phase:** 6
- **Affected files:**
  - `tools/retrieval_eval_bench.py:127-146`
  - `xyzgl/prompting.py:52-64`
  - `xyzgl/grounding/corpus.py:132-203`

**Problem:** The bench directly calls `load_corpus(Path(args.grounding_dir))`. Runtime prompt construction first resolves with `_resolve_within(repo_root, rel_path)` and rejects symlinks whose target escapes the repo. The bench is also CWD-sensitive: default `--bench` and `--grounding-dir` are plain relative paths, and it allocates `run_dir` before validating either path, leaving orphan dirs on failure.

**Expected:** The bench's grounding-dir validation matches runtime `_resolve_within(...)`. Built-in defaults resolve relative to `_REPO_ROOT`. Failure artifacts are always cleaned up.

**Fix:** Align bench validation with runtime. Resolve defaults against `_REPO_ROOT`. Allocate run directory only after inputs are confirmed valid.

---

---

### BUG-61: `harness_turn.py --keep-storage` is a dead flag

- **Severity:** Low
- **Phase:** 4
- **Affected file:**
  - `tools/harness_turn.py:86, 132-135`

**Problem:** `--keep-storage` is parsed, but the only code path behind it is a stub `pass`. The output bundle is identical whether the flag is present or not.

**Expected:** The flag is either implemented or removed.

**Fix:** Implement real storage preservation or remove the flag.

---

---

### BUG-63: `ai_property_turn_fuzzer.md` is out of sync with actual tool outputs

- **Severity:** Low
- **Phase:** 6
- **Affected files:**
  - `documentation/tools/ai_property_turn_fuzzer.md:25-28`
  - `tools/property_turn_fuzzer.py:48-78`

**Problem:** The documentation says the tool outputs only `property_fuzz_report.json`. The tool actually writes `property_fuzz_report.json`, `property_fuzz_summary.md`, and `run.json`.

**Expected:** Documentation matches the emitted file set.

**Fix:** Update the documentation.

---

---

### BUG-64: `tools/secret_scanner.py` silently skips large text files

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/secret_scanner.py:87-92, 149-160`

**Problem:** `_is_text()` returns `False` for any file over `2_000_000` bytes. The scanner never reaches the read/scan path for large text blobs. The failure is silent: the tool reports success rather than incomplete coverage.

**Expected:** Large text files are scanned or the tool reports `INCOMPLETE` when size limits prevent full coverage.

**Fix:** Distinguish "large text skipped" from "not text", and fail or mark `INCOMPLETE` when size limits prevent a full enforced scan.

---

---

### BUG-66: `protocol_drift_radar.py` never scans session `eval.next_action`

- **Severity:** High
- **Phase:** 6
- **Affected file:**
  - `tools/protocol_drift_radar.py:117-135, 153-181`

**Problem:** The session collector scans `teach.teaching_block`, `teach.question`, `eval.evaluation`, and `mirror.answer`. It does not scan `eval.next_action`, even though that is another tutor-authored field. The bundle demonstrates that replay diff treats such a mutation as meaningful while the drift radar misses it.

**Expected:** `eval.next_action` is included in the tutor-side text collection.

**Fix:** Include `eval.next_action` in the session text collection.

---

---

### BUG-68: `property_turn_fuzzer.py` overstates coverage when `--max-len=0`

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/property_turn_fuzzer.py:148-150, 214`

**Problem:** `--max-len` accepts `0`. The builtin generator therefore produces only empty strings, but the summary still reports `cases_executed = args.cases`. Twenty nominal cases collapse to one effective test input.

**Expected:** Zero-length fuzz budgets are rejected or reported as degenerate coverage.

**Fix:** Reject `--max-len < 1`, or track unique inputs and report effective coverage separately.

---

---

### BUG-71: `mirror_leakage_detector.py` accepts arbitrary top-level JSON with a `turns` array

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/mirror_leakage_detector.py:110-130`

**Problem:** After optional witness unwrapping, the detector accepts any top-level dictionary that exposes a `turns` array. It does not require the stricter report/session schema used elsewhere.

**Expected:** Only recognized report containers are accepted.

**Fix:** Tighten input validation to require an approved report/session shape.

---

---

### BUG-73: `protocol_drift_radar.py` ignores `session_summary.md` in directory scans

- **Severity:** Medium
- **Phase:** 6
- **Affected file:**
  - `tools/protocol_drift_radar.py:90-145`

**Problem:** Directory scans inspect `turn_report.json` and `session_report.json` but not `session_summary.md`. The markdown summary is a user-facing artifact that can carry drift evidence absent from the JSON.

**Expected:** Directory scans include `session_summary.md` or clearly state it is out of scope.

**Fix:** Add `session_summary.md` to the scanned artifact set in directory mode.

---

---

### BUG-76: `tools/ci_gate.py` sanitizes child stdout before extracting the session run dir, so it cannot locate the run bundle it just created

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_2nd_pass_2026-03-06.md` issue 1
- **Affected file:**
  - `tools/ci_gate.py`

**Problem:** The harness-session step can exit `0`, but `ci_gate.py` still records `INCOMPLETE: could not locate session run dir` because it sanitizes absolute paths in child stdout before trying to parse the emitted run path. The real path is lost before extraction.

**Expected:** Internal path extraction uses raw child output. Only the user-facing stored tail should be sanitized.

**Fix:** Preserve both raw and sanitized stdout tails, extract run directories from the raw form, and persist only the sanitized form in CI-facing artifacts.

---

---

### BUG-77: `tools/apply_signal_fidelity_overlay.py` defaults to an overlay archive that is not actually shipped

- **Severity:** Low
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_2nd_pass_2026-03-06.md` issue 2
- **Affected files:**
  - `tools/apply_signal_fidelity_overlay.py`
  - `documentation/tools/ai_apply_signal_fidelity_overlay.md`
  - expected shipped overlay contents under `signal_fidelity_overlay/`

**Problem:** The tool's documented default workflow assumes a bundled archive at `signal_fidelity_overlay/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED.rar`, but the referenced file is not present in the repo snapshot. The out-of-the-box default run therefore returns `INCOMPLETE`.

**Expected:** The default workflow uses an overlay source that is actually shipped, or the docs clearly require the operator to provide one.

**Fix:** Ship the referenced default archive, switch the default to a shipped source, or remove the implicit default-source assumption from code and docs.

---

---

### BUG-78: `tools/coverage_gate.py` emits a non-canonical `coverage_raw.json` artifact

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_3rd_pass_2026-03-06.md` issue 1
- **Affected files:**
  - `tools/coverage_gate.py`
  - downstream checker: `tools/artifact_roundtrip.py`

**Problem:** `artifact_roundtrip.py --strict` reports `coverage_raw.json => changed: true`, which means `coverage_gate.py` is writing a JSON artifact that is not already in canonical form. That breaks the repository's own artifact-stability expectations.

**Expected:** All JSON artifacts emitted by `coverage_gate.py` are already canonical and survive strict artifact round-tripping unchanged.

**Fix:** Route `coverage_raw.json` generation through the canonical JSON writer and keep ordering/formatting stable across runs.

---

---

### BUG-79: `tools/artifact_roundtrip.py` ignores nested `child_runs/**/*.json` when given a run directory

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_3rd_pass_2026-03-06.md` issue 2
- **Affected file:**
  - `tools/artifact_roundtrip.py`

**Problem:** In directory mode the tool only checks top-level `*.json` files and skips recursive child artifacts under `child_runs/`. A run bundle can therefore contain unstable or malformed nested JSON while strict round-trip validation still reports success on the parent directory.

**Expected:** Directory mode validates all relevant JSON artifacts in the run bundle, including nested child-run outputs, or explicitly warns that recursive validation is out of scope.

**Fix:** Add recursive JSON discovery for run-directory validation, or introduce an explicit mode that walks child artifacts and fails when nested JSON is unstable.

---

---

### BUG-81: Multiple bug-finding tools emit non-canonical `run.json` artifacts and fail the repository's own strict round-trip checker

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_5th_pass_2026-03-06.md`
- **Affected files:**
  - `tools/atheris_fuzz_router.py`
  - `tools/redteam_injection_suite.py`
  - `tools/redteam_rag_poisoning_suite.py`
  - `tools/reground_cadence_verifier.py`
  - `tools/mirror_leakage_detector.py`
  - `tools/mirror_calibration_bench.py`

**Problem:** These tools can return `PASS`, but their emitted `run.json` files are written with raw `json.dumps(...)` instead of the canonical `write_json(...)` helper, so `tools/artifact_roundtrip.py --strict` flags the bundles as unstable. The repository's own artifact contract therefore fails on otherwise green tool runs.

**Expected:** Every tool-produced `run.json` is canonical, byte-stable JSON and survives strict artifact round-tripping unchanged.

**Fix:** Route `run.json` emission through the canonical JSON writer for every affected tool. Keep the same canonical settings used elsewhere (`indent=2`, `sort_keys=True`, trailing newline) so strict round-trip validation passes consistently.

---

---

### BUG-89: Default tutoring and grounding collapse distinct welding topics into the same generic uncited output

- **Severity:** High
- **Phase:** 2
- **Source:** `xyzgl_new_issues_report_round18.md`
- **Affected files:**
  - `xyzgl/welding_tutor.py`
  - `tools/harness_session.py`
  - `tools/seed_sweep.py`
  - `curriculum/manifest.json`

**Problem:** The shipped default experience does not preserve topic-specific or evidence-specific behavior. Two different default session nodes (`pos_1f_vs_2f` and `smaw_basic_arc`) serialize the same teaching block, unrelated single-turn prompts hash to the same reply, local grounding for the default graph always falls back to the lone `demo_fitup` source, and even grounded turns with snippets present emit no `[src:...:...]` citations. The result is a tutoring path that looks grounded and curriculum-aware in metadata while remaining behaviorally generic.

**Expected:** Distinct curriculum nodes and distinct welding questions produce different tutor content. The shipped local grounding corpus covers the default nodes, and grounded turns surface source citations whenever snippets are present.

**Fix:** Expand the default curriculum corpus to cover the default graph, condition tutor output on node/topic and retrieved evidence, and enforce citation emission when grounded snippets are supplied.

---

---

### BUG-91: Backend validation tools ignore stdout/stderr side effects and can leak secret-bearing output while reporting green or handled results

- **Severity:** High
- **Phase:** 6
- **Source:** `backend_probe_round21_new_issues_20260306.zip`
- **Affected files:**
  - `tools/backend_contract_probe.py`
  - `tools/backend_fault_injector.py`

**Problem:** The current backend validation tools check return shapes and fallback behavior but do not treat backend writes to stdout/stderr as contract violations. A backend can print secret-bearing text directly to process output and still receive a green contract `PASS` or a handled-fallback `pass: true` scenario result. The tools' own stdout/stderr can therefore leak secret-bearing output while the saved reports remain misleadingly clean.

**Expected:** Backends that write to stdout/stderr during probing or fault injection fail the validation, and the tools report only bounded side-effect metadata rather than raw leaked text.

**Fix:** Capture stdout/stderr around backend calls, fail on any non-empty captured side effects, and record only non-secret summary metadata such as presence/length booleans.

---

---

### BUG-94: `artifact_roundtrip.py --strict` can report process-level `FAIL` while leaving changed files marked `PASS`

- **Severity:** Medium
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round29.md`
- **Affected file:**
  - `tools/artifact_roundtrip.py`

**Problem:** Under `--strict`, the tool can exit with `FAIL: strict mismatch` while the per-file entry for a changed artifact still records `status: "PASS"`. That creates an internal contradiction between the process-level result and the machine-readable per-file status, so downstream consumers can misclassify a strict failure as a pass.

**Expected:** Per-file status is consistent with the strict-mode outcome. Any file that changed under a strict failure is marked `FAIL`, or the report uses an explicit top-level failure state that the per-file entries do not contradict.

**Fix:** Make per-file status reflect strict mismatches directly, and keep the top-level and per-file result models aligned.

---

---

### BUG-96: `harness_lattice.py` is a false-green sensitivity sweep that never checks whether lattice dimensions change the reply meaningfully

- **Severity:** Medium
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round31.md`
- **Affected files:**
  - `tools/harness_lattice.py`
  - `tools/lattice_lib.py`

**Problem:** The lattice sweep varies process, thickness, and defect combinations but still reports `PASS` when all cases collapse to the same generic reply. The tool only asserts generic shape properties such as non-empty reply, safety prefix, and determinism, so it can certify a behavior-sensitivity sweep even when none of the lattice dimensions materially influence the answer.

**Expected:** A behavior-sensitivity lattice either verifies that the reply changes with at least one declared lattice dimension or explicitly declares itself a generic shape/contract sweep instead of a behavior sweep.

**Fix:** Add semantic-delta assertions keyed to process / thickness / defect dimensions, or narrow the tool's claimed purpose and pass criteria to pure contract validation.

---

---

### BUG-97: `backend_contract_probe.py` misclassifies offline and local backend configuration defects because the no-network gate runs after backend construction

- **Severity:** Medium
- **Phase:** 6
- **Source:** `backend_probe_round28_new_issues_20260307.zip`
- **Affected file:**
  - `tools/backend_contract_probe.py`

**Problem:** The probe constructs the backend before applying the no-network policy and then treats `BackendConfigError` under `--allow-network` absence as `INCOMPLETE` too broadly. As a result, local defects such as `unknown_backend` are hidden as `INCOMPLETE` instead of `FAIL`, while real network backends like `gemini` can leak ambient credential/config errors instead of the stable `network backend disabled` classification.

**Expected:** Network-disabled backends are classified as a stable no-network `INCOMPLETE` before env-dependent backend construction, while local backend/config defects remain `FAIL`.

**Fix:** Classify backend families before instantiation, apply the no-network gate first for network backends, and reserve `INCOMPLETE` for intentionally disabled network paths rather than local config defects.

---

---

### BUG-105: Several standalone workflow tools still fail to reject malformed or no-op structured inputs before claiming success or crashing late

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_17th_pass_2026-03-07.md`
- **Affected files:**
  - `tools/doc_code_link_checker.py`
  - `tools/apply_signal_fidelity_overlay.py`
  - `tools/signal_fidelity_port.py`

**Problem:** `doc_code_link_checker.py` silently skips malformed non-dict entries inside `docs/AI_INDEX.json -> surfaces` and can still report `PASS` on corrupted index data. `apply_signal_fidelity_overlay.py` reports `PASS` for an empty overlay zip that copies zero files. `signal_fidelity_port.py` crashes on malformed `--plan` JSON instead of producing a controlled error. These are the same quality-gate failure pattern: malformed or operationally empty structured inputs are not validated before the tool claims success or falls over late.

**Expected:** Quality-gate and workflow tools fail closed on malformed structured inputs, reject empty/no-op overlays as invalid application attempts, and surface parse errors as controlled `INCOMPLETE`/`FAIL` outcomes rather than raw tracebacks.

**Fix:** Treat malformed `AI_INDEX.surfaces` entries as reportable problems, fail overlay application when zero files are copied from an archive input, and wrap plan-file JSON parsing in controlled validation that returns a stable non-success status.

---

---

### BUG-106: `secret_scanner.py` false-negatives standalone secret literals because the prefilter skips literal-only files, and the OpenAI key regex is stale for `sk-proj-...`

- **Severity:** High
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round34.md`
- **Affected file:**
  - `tools/secret_scanner.py`

**Problem:** `_scan_file()` short-circuits on a narrow marker-word prefilter (`api`, `key`, `secret`, `token`, etc.). A file containing only a raw secret literal such as `ghp_...`, `AKIA...`, or `AIza...` is skipped before regex scanning even though those secret families are already advertised in `_PATTERNS`. The OpenAI key matcher is also stale and misses modern `sk-proj-...` keys.

**Expected:** Small text files that contain candidate secret literals are scanned against the literal patterns even if they do not also contain marker words, and OpenAI key detection covers modern `sk-proj-...` variants in addition to older `sk-...` forms.

**Fix:** Remove or widen the prefilter so it cannot bypass literal-family detection for small text files, and update the OpenAI key regex family to include `sk-proj-...` style keys.

---

### BUG-107: `secret_scanner.py` assignment regexes are too narrow for common token alphabets and unquoted credentials

- **Severity:** High
- **Phase:** 6
- **Source:** `XYZGL_new_bug_report_round37.md`
- **Affected file:**
  - `tools/secret_scanner.py`

**Problem:** Even when the file clearly contains credential marker words and reaches the pattern scan, several assignment-style secret detectors are still too restrictive for real-world credentials. The current bearer-literal and generic token assignment patterns exclude common token characters such as `/`, `+`, and `.`, and password assignment detection only matches quoted values. As a result, obvious assignments like `authorization=Bearer ABCD/EFGH+...`, `api_key=ABCD/EFGH+...`, `secret=AAAA.BBBB...`, and unquoted `password=supersecret12345` can all pass as clean.

**Expected:** Assignment-style secret detection covers realistic token alphabets and common authoring conventions, including base64-like `/` and `+`, dot-delimited token segments, and both quoted and unquoted password assignments.

**Fix:** Broaden the bearer and generic assignment character classes to include `/`, `+`, and `.`, and add explicit support for unquoted password assignments or a shared assignment parser that handles both quoted and unquoted suspicious values.

---

### BUG-108: `prompt_snapshot_guard.py` validates only prompt hashes and ignores baseline contract drift in schema, case-set membership, and stored metadata

- **Severity:** Medium
- **Phase:** 6
- **Source:** `xyzgl_new_bug_report_25th_pass_2026-03-07.md`
- **Affected file:**
  - `tools/prompt_snapshot_guard.py`

**Problem:** When a baseline already exists and `--update` is not used, `prompt_snapshot_guard.py` enforces only `cases[*].sha256` for cases it rebuilds locally. It does not validate the baseline-level `schema_version`, does not detect stale extra baseline cases that are no longer part of the canonical case set, and ignores drift in the stored `length` and `meta` fields (`protocol_regrounded`, `grounding_enabled`) as long as the prompt hash still matches. The guard therefore treats a structurally stale or semantically drifted baseline as healthy.

**Expected:** Snapshot-guard validation treats the entire baseline contract as authoritative: the top-level schema identity is validated, the baseline case set must match the canonical built case set exactly, and stored per-case metadata such as length and prompt-mode flags must also match the rebuilt baseline.

**Fix:** Validate the top-level baseline schema version, compare both missing and extra case names, and enforce equality for all persisted per-case contract fields (`sha256`, `length`, and `meta`) instead of only the prompt hash.

---


## G. Grounding & Retrieval Integrity

### BUG-19: Grounding assembly stops at the first oversized snippet header

- **Severity:** High
- **Phase:** 2
- **Affected file:**
  - `xyzgl/grounding/prompting.py` ???????? `build_grounding()` uses `break` when budget exhausted

**Problem:** An oversized top-ranked snippet header starves all later eligible snippets. Additionally, overlong `source_id` or `source_title` values can consume the entire excerpt budget, making `max_excerpt_chars <= 0`, which causes the loop to break before emitting any grounding text. Retrieval validation stays green because it only checks ranked identities, not whether passages remain promptable.

**Expected:** Oversized snippets are skipped; later fitting snippets are still included. Oversized identifiers are clamped or elided.

**Fix:** Replace `break` with `continue` when a candidate cannot fit. Bound `source_id` and `source_title` in prompt headers.

---

---

### BUG-20: Absolute grounding paths silently disable grounding while metadata reports it enabled

- **Severity:** High
- **Phase:** 2
- **Affected files:**
  - `xyzgl/prompting.py` ???????? `grounding_enabled` computed from mode alone; absolute path rejected but metadata still reports `grounding_enabled=True`
  - `tools/redteam_rag_poisoning_suite.py` ???????? constructs invalid configuration; boundary check validates only marker pairing when markers exist, never requires markers to exist

**Problem:** Runtime claims grounding is enabled when no grounding block is present. `redteam_rag_poisoning_suite.py` can report `PASS` when grounding is completely absent because it only validates markers when they exist and never requires grounding markers to be present.

**Expected:** Invalid paths fail closed or set `grounding_enabled=False`. Security tooling verifies grounding actually occurred. Poisoning suite fails when grounding is expected but missing.

**Fix:** Make enablement reflect actual load state. Update poisoning suite to assert grounding markers exist.

---

---

### BUG-21: Grounding retrieval is poisonable via duplicate IDs, tie bias, source monoculture, keyword stuffing, and query-window truncation

- **Severity:** High
- **Phase:** 2
- **Affected files:**
  - `xyzgl/grounding/corpus.py` ???????? accepts duplicate non-empty `source_id`
  - `xyzgl/grounding/retrieval.py` ???????? lexicographic tie bias on `(-score, source_id, ordinal)`; no source diversity; `_MAX_QUERY_TOKENS = 256` hard-drops later unique tokens
  - `xyzgl/grounding/prompting.py` ???????? emits the returned snippets unchanged

**Problem:** Duplicate `source_id` aliases let poisoned content impersonate trusted sources. Lexicographic bias gives attacker-controlled IDs placement advantage. One source can dominate all slots. A short poisoned passage that mirrors exact query terms outranks legitimate content under Jaccard ranking. With `grounding_max_snippets=1`, the poisoned snippet becomes the only grounded passage. Long filler prefixes can consume the entire 256-token query window before discriminating terms appear. The grounding audit stays green through all these attacks.

**Expected:** Unique `source_id`. Neutral tie-breaking. Source diversity enforcement. Query-budget strategy that preserves suffix terms. Audit detects retrieval poisoning.

**Fix:** Reject duplicate `source_id` at load. Replace lexical tie-breaking. Cap snippets per source. Use a query-budget strategy that samples from prefix and tail. Add trust weighting or instruction-pattern penalty.

---

---

### BUG-46: 500-source corpus cap can silently drop relevant sources

- **Severity:** High
- **Phase:** 2 (via Phase 6 audit)
- **Affected areas:**
  - Grounding corpus loading ???????? hard-caps sources at 500
  - `tools/grounding_injection_audit.py` ???????? only checks marker integrity when grounding text exists

**Problem:** If matching content exists only in the 501st source, grounding returns no snippets. The audit still reports `PASS`.

**Expected:** Source caps are documented. Audits detect absent grounding.

**Fix:** Raise or warn when source count exceeds cap. Audit should verify at least one snippet was produced.

---

---

### BUG-47: 20,000-passage cap can be exhausted by filler sources before target content loads

- **Severity:** High
- **Phase:** 2
- **Affected areas:**
  - Grounding corpus loading ???????? 20,000-passage budget consumed in source order
  - `tools/grounding_injection_audit.py` ???????? still returns `PASS` when grounding disappears

**Problem:** Oversized filler sources consume the entire passage budget before later target sources are read. This is a positional suppression vector.

**Expected:** Passage caps cannot be weaponized. Audits detect empty grounding.

**Fix:** Distribute passage budget more equitably or warn when exhausted before all sources load.

---

---

### BUG-48: Duplicate root keys in `manifest.json` can zero out the corpus

- **Severity:** High
- **Phase:** 2
- **Affected areas:**
  - Corpus manifest parsing ???????? duplicate JSON root keys trigger rejection, collapsing corpus to empty
  - `tools/grounding_injection_audit.py` ???????? stays green on empty grounding

**Problem:** A malformed manifest with two root-level `sources` keys disables grounding completely. Audit still returns `PASS`.

**Expected:** Duplicate root keys produce explicit error. Audit detects absent grounding.

**Fix:** Surface manifest parse errors explicitly. Audit should fail when grounding is configured but absent.

---

---

### BUG-58: Grounding headers trust raw manifest `source_id` and `source_title`

- **Severity:** High
- **Phase:** 2
- **Affected files:**
  - `xyzgl/grounding/prompting.py:71-86`
  - `xyzgl/grounding/corpus.py:162-172`

**Problem:** Manifest `id` and `title` are loaded verbatim into `SourceSpec`. `build_grounding()` emits `[src:{source_id}:{ordinal}] {source_title}\n` headers with no sanitization. A poisoned `source_id` can forge trusted-looking `[src:...]` citations. A poisoned `source_title` can inject uncited attacker text into the grounding block header.

**Expected:** Manifest ids/titles are constrained to a safe character set or sanitized before building prompt headers.

**Fix:** Constrain manifest ids/titles or sanitize them before building prompt headers.

---

---

### BUG-69: Oversized grounding manifests silently disable grounding while the audit still passes

- **Severity:** High
- **Phase:** 2
- **Affected files:**
  - `xyzgl/grounding/corpus.py:8, 116-129, 141-151`
  - `tools/grounding_injection_audit.py:117-132, 148-166`

**Problem:** `_read_text_limited()` returns `None` when the manifest exceeds `MAX_MANIFEST_BYTES`. `load_corpus()` returns an empty corpus. The audit compares direct grounding output with prompt output and can report `PASS` when both are empty.

**Expected:** Oversized manifests produce explicit failure state. Audit fails when expected grounding disappears.

**Fix:** Surface manifest-too-large error. Audit should treat missing grounding as failure when grounding was requested.

---

---

### BUG-70: Hard no-overlap chunk splitting breaks retrieval at passage boundaries

- **Severity:** Medium
- **Phase:** 2
- **Affected files:**
  - `xyzgl/grounding/corpus.py:62-70, 89-113`

**Problem:** Text is split into fixed-size chunks with no overlap. A clean answer that straddles a chunk boundary can be split while a shorter poison chunk remains intact, causing the poison chunk to outrank the fragmented answer.

**Expected:** Chunking preserves enough overlap or semantic continuity to avoid boundary-driven retrieval corruption.

**Fix:** Introduce overlap or smarter segmentation.

---

---

### BUG-80: Whitespace-only blank lines are not treated as paragraph breaks in grounding corpora, so poison and clean context can collapse into one oversized paragraph

- **Severity:** High
- **Phase:** 2
- **Source:** `rag_poisoning_round12_bundle_20260306.zip` issue `ISSUE-20260306-202`
- **Affected file:**
  - `xyzgl/grounding/corpus.py`

**Problem:** `_iter_paragraphs()` recognizes only the exact delimiter `\n\n`. Blank lines containing spaces or tabs are ignored, so poison and clean paragraphs can be merged into one oversized paragraph. When that merged paragraph is later hard-split, retrieval can return a chunk that starts with poison text while still containing enough clean tokens to satisfy the bench.

**Expected:** Whitespace-only blank lines behave as paragraph boundaries, preserving clean/poison separation and preventing accidental paragraph collapse.

**Fix:** Treat blank lines with spaces or tabs as paragraph separators in `_iter_paragraphs()` before chunking and retrieval.

---

### BUG-88: `grounding_injection_audit.py` validates an unclamped query while runtime grounding uses the clamped query

- **Severity:** High
- **Phase:** 2 (via Phase 6 audit)
- **Source:** `grounding_injection_new_issues_round21_20260306.zip`
- **Affected files:**
  - `tools/grounding_injection_audit.py`
  - `xyzgl/router.py`
  - `xyzgl/prompting.py`

**Problem:** The audit calls grounding construction on the full raw query text, but the live runtime path first normalizes and clamps user input to `max_chars_in` before prompt construction. If the only retrieval-relevant token lies past the runtime cap, the audit can report `PASS` with grounded snippets while the routed turn gets zero grounding.

**Expected:** Audit and runtime validate grounding over the same effective user query after the same normalization and length clamp.

**Fix:** Make the audit reuse runtime preprocessing or build its verdict from the same capped query that `route_turn()` actually uses. The prompt-building path should also derive grounding from the normalized/capped user text rather than a raw direct-call variant.

---

### BUG-92: `manifest.json` source paths using Windows separators silently drop valid grounding sources on POSIX

- **Severity:** High
- **Phase:** 2
- **Source:** `rag_poisoning_round21_bundle_20260306.zip`
- **Affected file:**
  - `xyzgl/grounding/corpus.py`

**Problem:** A manifest entry such as `sources\doc.md` is treated as a literal filename instead of a relative path, so valid sources load on Windows-style manifests but disappear on POSIX. Grounding and retrieval can therefore go empty on cross-platform corpora without an explicit error.

**Expected:** Manifest source paths are normalized consistently across platforms and valid relative source entries load regardless of slash direction.

**Fix:** Normalize manifest path strings before path resolution so backslashes are treated as separators rather than literal path characters.

---

---

### BUG-93: Retrieval and evaluation can certify snippets whose shown excerpt omits the actual matching evidence

- **Severity:** High
- **Phase:** 2
- **Source:** `rag_poisoning_round21_bundle_20260306.zip`
- **Affected files:**
  - `xyzgl/grounding/retrieval.py`
  - `tools/retrieval_eval_bench.py`

**Problem:** Retrieval can rank a source because the passage contains matching terms, then emit an excerpt clipped from the document head that omits those matched terms entirely. `retrieval_eval_bench.py` still records `PASS` because it checks returned `source_id` values rather than whether the shown excerpt actually carries the query evidence. That allows the system to present and certify evidence-less snippets.

**Expected:** Retrieved excerpts are anchored around matched terms, and evaluation fails when the returned snippet text does not contain the evidence that justified retrieval.

**Fix:** Build excerpts around the actual matched window rather than the document head, and make the bench verify evidence-bearing snippet text instead of source IDs alone.

---

### BUG-98: `redteam_rag_poisoning_suite.py` boundary checks accept malformed structured prompt layouts as PASS

- **Severity:** High
- **Phase:** 6
- **Source:** `rag_poisoning_round24_bundle_20260307.zip`
- **Affected file:**
  - `tools/redteam_rag_poisoning_suite.py`

**Problem:** The suite's boundary oracle only checks a loose subset of marker conditions. It can still report `PASS` when structured protocol/grounding blocks close after `USER_OPEN`, when duplicate open markers appear with only one close, or when a second protocol block is appended after the user section. That leaves materially malformed prompt structure certified as safe by the red-team tool.

**Expected:** Boundary validation enforces exact structured layout invariants: balanced counts, close-before-user ordering, and no duplicate or post-user protocol/grounding blocks.

**Fix:** Count markers rather than testing only presence, enforce a single balanced block for each structured section, and reject any protocol/grounding markers that appear after the user block begins.

---

---

### BUG-99: `retrieval_eval_bench.py` does not validate benchmark-case field types and can false-pass or crash on malformed rows

- **Severity:** High
- **Phase:** 6
- **Source:** `rag_poisoning_round24_bundle_20260307.zip`
- **Affected file:**
  - `tools/retrieval_eval_bench.py`

**Problem:** The bench stringifies non-string `query` values, blindly iterates scalar or string `expect_source_ids`, and therefore can both false-pass malformed cases and crash outright. A malformed case can be certified as a valid success because Python stringification preserves retrieval terms, or a scalar/string expectation can char-split into incorrect source-id matching semantics.

**Expected:** Benchmark-case rows are schema-validated before evaluation. `query` must be a string, `expect_source_ids` must be a list of strings, and malformed rows must fail cleanly as invalid input rather than altering evaluation semantics.

**Fix:** Validate input row types up front and return `INCOMPLETE` / `FAIL` for malformed cases before any retrieval logic runs.

---

---

### BUG-102: `build_tutor_prompt()` silently re-clamps `grounding_max_snippets` to 64, so injected grounding can disagree with both config and direct grounding output

- **Severity:** High
- **Phase:** 2 (via Phase 6 audit)
- **Source:** `grounding_injection_new_issues_round31_20260307.zip`
- **Affected files:**
  - `xyzgl/prompting.py`
  - `xyzgl/config.py`
  - `tools/grounding_injection_audit.py`

**Problem:** The config accepts `grounding_max_snippets` values up to 128, and direct `build_grounding(..., max_snippets=N)` respects that higher bound, but `build_tutor_prompt()` silently re-clamps the injected prompt path to 64 snippets. Under higher configured snippet counts, the audit-visible grounding output and the final tutor prompt diverge even when they are supposed to represent the same grounding set.

**Expected:** The configured snippet cap is enforced consistently across direct grounding generation, prompt injection, and grounding audit tooling. If 100 snippets are configured and available, the injected prompt path should not silently drop labels `s064` onward.

**Fix:** Remove the hidden local 64-snippet clamp from `build_tutor_prompt()` or move the canonical snippet bound into one shared config/runtime constant used by both direct grounding and injected prompt assembly.

---

---


## Enrichment Log (All Rounds)

### BUG-17 enrichment: mirror/protocol detection blind spots remain broader than the final master currently lists

Additional evidence folded into `BUG-17`:
- `behavior_drift_replay_bundle_round13.zip` finding 2: `protocol_drift_radar.py` ignores nested `prompt_meta.backend_error` text even when it carries explicit protocol-role leakage
- `graph_mirror_audit_round11_20260306.zip` findings `M-11-01`, `M-11-02`, and `M-11-03`: missing phrase coverage for `Be sure to ...` and `The key is to ...`, plus a false positive for polite learner text containing `Please ...`

These were folded into `BUG-17` because they are the same underlying class: detection tools are still too narrow in both field coverage and phrase modeling.

### BUG-18 enrichment: graph checker still diverges from real loadability constraints

Additional evidence folded into `BUG-18`:
- `graph_mirror_audit_round11_20260306.zip` finding `G-11-02`: `graph_invariant_checker.py` returns `PASS` for a schema-valid graph that the application will never load because `xyzgl.knowledge.graph.load_graph()` rejects graphs above `MAX_GRAPH_BYTES`

This is treated as an enrichment of `BUG-18` because it is another concrete case of the checker certifying artifacts that runtime graph loading rejects.

### BUG-20 enrichment: the round-12 RAG suite still has the known false-PASS fixture defect

Additional evidence folded into `BUG-20`:
- `rag_poisoning_round12_bundle_20260306.zip` issue `ISSUE-20260306-201` confirms the suite still builds a non-loadable fixture and reports `PASS` without real grounded poison in the prompt

### BUG-23 enrichment: `harness_turn.py` still writes raw summary input while the report stores normalized input

Additional evidence folded into `BUG-23`:
- `xyzgl_turn_fresh_issues_report_12.md` issue 1 shows `turn_report.json.payload.turn_result.input` using NFC-normalized text while `turn_summary.md` still renders raw `args.text`

### BUG-44 enrichment: `property_turn_fuzzer.py` can silently drop executed result rows while still returning `PASS`

Additional evidence folded into `BUG-44`:
- `xyzgl_turn_fresh_issues_report_12.md` issue 2 shows `cases_executed = 2101`, `len(results) = 2000`, `results_dropped = 101`, and `overall = "PASS"`

This is folded into `BUG-44` because it is the same evidence-truncation family: executed campaign evidence is dropped without a corresponding incomplete/failure state.

### BUG-46 enrichment: invalid manifest entries can consume the 500-source budget before validation

Additional evidence folded into `BUG-46`:
- `grounding_injection_new_issues_round15_20260306.zip` issue `ISSUE-20260306-983` shows that 500 invalid `sources[]` entries can exhaust the cap before a later valid source is even considered

This is treated as an enrichment of `BUG-46` because it is the same core cap-enforcement defect, with a stronger exploit path.

### BUG-62 enrichment: env-only strictness switches are still missing from tool artifacts beyond `harness_turn.py`

Additional evidence folded into `BUG-62`:
- `xyzgl_turn_fresh_issues_report_12.md` issue 3 shows that `DAEDALUS_REQUIRE_REAL_BACKENDS` changes `property_turn_fuzzer.py` behavior materially, but the saved `run.json` still does not record that strictness switch

### BUG-70 enrichment: hard chunk-boundary retrieval failures remain reproducible through multiple boundary shapes

Additional evidence folded into `BUG-70`:
- `rag_poisoning_round12_bundle_20260306.zip` issue `ISSUE-20260306-203` demonstrates a clean token split across the 800-character boundary, allowing a poisoned intact token source to outrank it
- `grounding_injection_new_issues_round16_20260306.zip` issue `ISSUE-20260306-1005` shows the same boundary problem when a relevant keyword crosses the hard 800-character split and becomes unretrievable

### BUG-73 enrichment: `protocol_drift_radar.py` session-summary blind spot is now confirmed by a separate replay bundle

Additional evidence folded into `BUG-73`:
- `behavior_drift_replay_bundle_round13.zip` finding 1 was the evidence source that summary drift can be hidden even when the user-facing tutor question diverges materially from the witness payload

### BUG-11 enrichment: `harness_turn.py` secret leakage still misses modern token and key patterns

Additional evidence folded into `BUG-11` from `xyzgl_turn_fresh_issues_report_15.md`:
- PEM-style private key blocks still pass through into `turn_report.json` and `turn_summary.md`
- newer GitHub token families such as `gho_`, `ghs_`, and `github_pat_` are not redacted by the current generic secret pattern set

This remains an enrichment of `BUG-11`, not a new master bug, because it is the same underlying artifact-secret-leak defect.

### BUG-34 enrichment: `property_turn_fuzzer.py` still emits non-canonical `run.json`

`xyzgl_new_bug_report_5th_pass_2026-03-06.md` reconfirms the existing `BUG-34` instance on `property_turn_fuzzer.py`. That evidence was folded into the existing bug instead of counted again.

### BUG-36 enrichment: `property_turn_fuzzer.py` still cannot synthesize important secret-leak payload classes

Additional evidence folded into `BUG-36` from `xyzgl_turn_fresh_issues_report_15.md`:
- the generator cannot produce PEM private-key markers
- the generator cannot produce newer GitHub token prefixes such as `gho_`

This remains part of the existing generator-coverage blind spot tracked under `BUG-36`.

### BUG-62 enrichment: env-only strictness still changes artifact semantics without being recorded in fuzzer bundles

Additional evidence folded into `BUG-62` from `xyzgl_turn_fresh_issues_report_15.md`:
- `DAEDALUS_REQUIRE_REAL_BACKENDS` materially changes `property_turn_fuzzer.py` outcomes, but the saved `run.json` does not record that strictness switch

### BUG-11 enrichment: `harness_turn.py` still misses newer token families and OpenSSH private-key blocks

Additional evidence folded into `BUG-11`:
- `xyzgl_turn_fresh_issues_report_17.md` confirms raw leakage of `github_pat_...`, `ghs_...`, `glpat-...`, `xoxp-...`, and full `BEGIN OPENSSH PRIVATE KEY` blocks into both `turn_report.json` and `turn_summary.md`

This is the same underlying single-turn secret-redaction defect already tracked in the master, with newly verified leak classes.

### BUG-12 enrichment: the default session harness fixture still self-closes nodes and leaves key learner-state branches untested

Additional evidence folded into `BUG-12`:
- `xyzgl_new_issues_report_round16.md` shows the default simulator answers satisfy `required_keywords` for all three default nodes on the first pass
- the same report shows default harness runs remain stuck in `frustrated` because simulated answers never reach the `flow` threshold, and the slow-typing branch is unreachable because the harness always supplies `typing_ms = 4500`

This is treated as enrichment of `BUG-12` because it is the same harness-fixture class: the default simulator still closes nodes too quickly and still does not cover meaningful session-state branches.

### BUG-13 enrichment: `seed_sweep.py` still fails as a false proxy under real-backend misconfiguration

Additional evidence folded into `BUG-13`:
- `xyzgl_new_issues_report_round16.md` shows `tools/seed_sweep.py` raising uncaught `BackendConfigError` under `DAEDALUS_TUTOR_BACKEND=gemini`, returning exit `1` and leaving behind a fresh empty run directory instead of a structured `INCOMPLETE` result

This is the same broader sweep-artifact defect already tracked in the master: the tool remains a noisy proxy that masks runtime/backend failure classes instead of reporting them cleanly.

### BUG-17 enrichment: mirror leakage detection still misses tutor-style coaching phrased as polite questions

Additional evidence folded into `BUG-17` from `graph_mirror_audit_round14_20260306.zip`:
- `ISSUE-20260306-144`: `Can you ...?` instructional question passes
- `ISSUE-20260306-145`: `Would you ...?` coaching question passes
- `ISSUE-20260306-146`: `Have you tried ...?` coaching prompt passes

These are all the same mirror-role leakage class already tracked in the master: the detector's phrase model remains too narrow for obvious tutor-style coaching variants.

### BUG-18 enrichment: graph invariant checker still certifies artifacts that runtime silently rewrites

Additional evidence folded into `BUG-18` from `graph_mirror_audit_round14_20260306.zip`:
- `ISSUE-20260306-141`: empty-but-schema-valid `title` passes even though core rewrites it to `node_id`
- `ISSUE-20260306-142`: blank `required_keywords` entries pass even though core silently drops them
- `ISSUE-20260306-143`: blank `fragility_flags` entries pass even though core silently drops them

This is the same checker/runtime-divergence defect family already captured by `BUG-18`: the validator still certifies graph artifacts that the live loader normalizes into a materially different structure.

### BUG-36 enrichment: `property_turn_fuzzer.py` still cannot synthesize important secret-leak payload classes

Additional evidence folded into `BUG-36`:
- `xyzgl_turn_fresh_issues_report_17.md` shows `_gen_case()` still cannot synthesize `github_pat_`, `ghs_`, `glpat-`, `xoxp-`, or `BEGIN OPENSSH PRIVATE KEY`, so normal green fuzz runs still miss those leak classes entirely

This is the same fuzz-coverage blind spot already tracked in the master.

### BUG-40 enrichment: the malformed `--issue` acceptance bug still affects many more tools than the master explicitly lists

Additional evidence folded into `BUG-40` from `xyzgl_new_bug_report_6th_pass_2026-03-06.md`:
- confirmed additional affected tools include `apply_signal_fidelity_overlay.py`, `atheris_fuzz_router.py`, `graph_invariant_checker.py`, `property_turn_fuzzer.py`, `redteam_injection_suite.py`, `redteam_rag_poisoning_suite.py`, `retrieval_eval_bench.py`, and `seed_sweep.py`

No new defect was created here because this is the same already-tracked issue-id validation failure class.

### BUG-45 enrichment: `targeted_sweep.py` still sanitizes child output before extracting run paths

Additional evidence folded into `BUG-45`:
- `xyzgl_new_bug_report_6th_pass_2026-03-06.md` reproduces the same `sanitize-then-parse` path loss on `tools/targeted_sweep.py` that the master already tracks

This report did not add a new bug because it reconfirms the exact existing failure mode.

### BUG-83 enrichment: the backend negative-latency runtime acceptance bug was independently reconfirmed

Additional evidence folded into `BUG-83`:
- `backend_probe_round18_new_issue_20260306.zip` reconfirms that runtime paths still accept `latency_ms = -1` results as success even though contract probing rejects them

This bundle did not add a new defect because it is the same runtime metadata-validation bug already captured by `BUG-83`.

### BUG-01 enrichment: non-strict tutor fallback is still independently failing in both router and teach-phase code paths

Additional evidence folded into `BUG-01` from `backend_probe_findings_20260306.zip`:
- missing Gemini credentials still raise instead of degrading to stub
- unknown tutor backend names still raise instead of degrading to stub
- `backend_contract_probe.py` can stay green while the end-to-end router/orchestrator fallback path is red

This bundle did not add a new defect because it is the same already-tracked tutor strictness bug and the same contract-vs-runtime mismatch family.

### BUG-13 enrichment: `seed_sweep.py` still hides protocol and grounding miswiring when the stub reply stays stable

Additional evidence folded into `BUG-13` from `xyzgl_new_issues_report_round17.md`:
- broken `DAEDALUS_PROTOCOL_PATH` can alter routed `prompt_meta.protocol_path` without changing the saved `seed_sweep_report.json`
- broken local grounding (`DAEDALUS_GROUNDING_MODE=local`, missing `DAEDALUS_GROUNDING_DIR`) can also leave the saved sweep artifacts indistinguishable from a healthy run once `run_id` and `issue_id` are normalized away

This is the same false-proxy artifact class already tracked in the master: the sweep can hide meaningful routed-turn differences and therefore cannot be trusted as a faithful summary of live behavior.

### BUG-16 enrichment: `repro_replay_diff.py --strict` still omits concrete provenance fields

Additional evidence folded into `BUG-16` from `behavior_drift_replay_bundle_round18.zip`:
- strict replay still ignores tampering in `payload.turn_result.effective_backend`
- strict replay still ignores tampering in `payload.turn_result.requested_backend`
- strict replay still ignores tampering in `payload.turn_result.tutor_meta`

This is the same replay-provenance blind spot already tracked in the master, now with a minimal forged-turn repro that names the exact omitted fields.

### BUG-17 enrichment: mirror and protocol drift detection still fail on non-English and confusable-character tutor leakage

Additional evidence folded into `BUG-17`:
- `graph_mirror_audit_round15_20260306.zip` shows `mirror_leakage_detector.py` missing explicit Spanish and Japanese tutor imperatives
- `behavior_drift_replay_bundle_round18.zip` shows `protocol_drift_radar.py` returning `PASS` when `As your tutor` is disguised with Cyrillic confusable characters

This is the same detector-fragility family already tracked in the master: phrase coverage and normalization remain too narrow for obvious role-crossing variants.

### BUG-18 enrichment: graph invariant checking still diverges from runtime normalization in both directions

Additional evidence folded into `BUG-18` from `graph_mirror_audit_round15_20260306.zip`:
- `node_id` values with trailing spaces pass even though runtime trims them on round-trip
- `title` values with surrounding spaces pass even though runtime trims them on round-trip
- whitespace-padded `required_keywords` and `fragility_flags` pass even though runtime trims them on round-trip
- `last_verified_turn = -2` fails even though the shipped schema accepts it and runtime round-trips it unchanged

This is the same checker/runtime divergence bug already tracked in the master, with new examples of both false negatives and false positives.

### BUG-11 enrichment: `harness_turn.py` still misses more modern credential families

Additional evidence folded into `BUG-11`:
- `xyzgl_turn_fresh_issues_report_19.md` confirms leakage of `sk_live_`, `ASIA`, `ghu_`, `npm_`, and `xoxs-` tokens into both `turn_report.json` and `turn_summary.md`
- `xyzgl_turn_fresh_issues_report_20.md` confirms additional leakage of `hf_`, `sk-ant-`, `xapp-`, and `ya29.` token families into both artifacts

This remains the same single-turn secret-redaction defect already tracked in the master.

### BUG-17 enrichment: protocol drift scanning still misses nested session backend-error text

Additional evidence folded into `BUG-17` from `behavior_drift_replay_bundle_round19.zip`:
- session scans still ignore nested `teach.prompt_meta.backend_error` and `eval.prompt_meta.backend_error`, allowing explicit role-confusion text in those fields to pass with zero findings

This is the same detector-field-coverage blind spot already tracked in the master.

### BUG-21 enrichment: retrieval still loses discriminating evidence at a hard passage-token boundary

Additional evidence folded into `BUG-21` from `rag_poisoning_round21_bundle_20260306.zip`:
- `retrieve_snippets` can ignore relevant tail terms after the first 512 unique passage tokens, so a long passage becomes effectively unretrievable once the discriminating evidence falls beyond that boundary

This is the same retrieval-window truncation family already tracked in the master, now confirmed on the passage-token side as well as the query side.

### BUG-25 enrichment: `property_turn_fuzzer.py` still collapses materially different mirror executions into indistinguishable PASS bundles

Additional evidence folded into `BUG-25`:
- `xyzgl_turn_fresh_issues_report_19.md` shows raw-vs-redacted mirror privacy runs producing identical `property_fuzz_report.json` and `run.json` payloads after normalizing only `run_id` and `issue_id`
- `xyzgl_turn_fresh_issues_report_20.md` shows mirror-disabled and mirror-enabled runs producing identical `property_fuzz_report.json`, `property_fuzz_summary.md`, and `run.json` outputs
- the same round-20 report shows that mirror-enabled fuzzer artifacts still preserve no `mirror_prediction`, `mirror_meta`, or any marker that the mirror path was exercised at all

This is the same coarse-shape artifact bug already tracked in the master: the fuzzer still collapses materially different executions into indistinguishable PASS bundles.

### BUG-36 enrichment: the built-in turn fuzzer still cannot synthesize newly confirmed leaked token families

Additional evidence folded into `BUG-36`:
- `xyzgl_turn_fresh_issues_report_19.md` shows `_gen_case()` still cannot synthesize `sk_live_`, `ASIA`, `ghu_`, `npm_`, or `xoxs-`
- `xyzgl_turn_fresh_issues_report_20.md` shows `_gen_case()` still cannot synthesize `sk-ant-`, `xapp-`, or `ya29.` token families

This remains the same generator-coverage blind spot already tracked in the master.

### BUG-59 enrichment: `retrieval_eval_bench.py` default paths are still CWD-relative and still leave empty run dirs on invalid defaults

Additional evidence folded into `BUG-59` from `rag_poisoning_round21_bundle_20260306.zip`:
- the bench's shipped default paths still resolve relative to the caller CWD instead of the repo root
- the tool still allocates a run directory before validating those defaults, leaving an empty artifact dir on failure

This is the same bench/runtime path-resolution divergence already tracked in the master.

### BUG-62 enrichment: env-only mirror privacy switches still change artifact semantics without being recorded

Additional evidence folded into `BUG-62`:
- `xyzgl_turn_fresh_issues_report_19.md` shows `DAEDALUS_MIRROR_SEND_USER_CONTENT` changing `harness_turn.py` runtime behavior (`mirror_meta.prompt_mode`) while the saved config remains identical across runs
- the same report shows `property_turn_fuzzer.py` collapsing raw-vs-redacted mirror privacy runs to identical artifacts with no recorded runtime-mode distinction

This is the same env-only artifact-self-description defect already tracked in the master.

### BUG-13 enrichment: `seed_sweep.py` still certifies stability while missing real turn-index instability from protocol cadence

Additional evidence folded into `BUG-13` from `xyzgl_new_issues_report_round23 (3).md`:
- the same fit-up input flips from the correct fit-up correction on turn `4` to the generic fallback on turn `5` at a valid prompt budget
- at a slightly different budget, the same turn-`4` to turn-`5` transition flips into the empty-input fallback instead
- with local grounding enabled, an arc-length query can jump from generic fallback on turn `4` to the wrong-topic fit-up correction on turn `5`
- despite those adjacent-turn changes, `seed_sweep.py` still returns `PASS` with `unique_replies = 1` because it sweeps seeds rather than turn index

This is the same false-proxy defect already tracked in the master: the tool can still report stable behavior while hiding meaningful routed-turn instability.

### BUG-17 enrichment: drift scanning still misses tutor-role leakage in grounding snippets

Additional evidence folded into `BUG-17` from `behavior_drift_replay_bundle_round22.zip`:
- `protocol_drift_radar.py` still returns `PASS` when explicit tutor-role instructions are injected into `prompt_meta.grounding.snippets[*].text`

This is the same detector-field-coverage blind spot already tracked in the master, now extended to retrieved grounding text that directly conditions the tutor prompt.

### BUG-22 enrichment: `selfcheck.py` still silently ignores repo-style CLI args and does not participate in the standard tool contract

Additional evidence folded into `BUG-22` from `XYZGL_new_bug_report_round29.md`:
- `python tools/selfcheck.py --issue ISSUE-20260307-908` still exits `0/PASS`
- the tool does not parse `--issue`, does not reject unknown args, and does not emit a standard run bundle

This strengthens the existing quality-gate defect: `selfcheck.py` remains a low-signal special-case utility that can mislead automation into thinking an issue-scoped repo-tool check actually ran.

### BUG-25 enrichment: `property_turn_fuzzer.py` still collapses materially different grounding and protocol executions into identical PASS artifacts

Additional evidence folded into `BUG-25` from `xyzgl_turn_fresh_issues_report_24 (1).md`:
- grounding fully off vs local grounding with retrieved snippets still produces identical `property_fuzz_report.json` and `run.json` after normalizing IDs
- zero grounding snippets (`DAEDALUS_GROUNDING_MAX_SNIPPETS=0`) vs real retrieved grounding still produces identical PASS bundles
- different protocol files (`STABLE/ROLE_PROTOCOL.md` vs `README.md`) still produce identical PASS bundles

This is the same coarse-shape artifact bug already tracked in the master: the fuzzer still omits the prompt-side metadata needed to distinguish materially different executions.

### BUG-30 enrichment: `backend_fault_injector.py` still green-lights oversized fallback error payloads

Additional evidence folded into `BUG-30` from `backend_probe_round25_new_issues_20260306 (4).zip`:
- `_scenario()` still records `pass: true` for handled fallback cases even when `backend_error` is arbitrarily large
- the round-25 focused repro confirms the stock injector does not assert bounded fallback error metadata

This remains part of the injector's existing false-positive hole: the tool still misses an important fallback invariant.

### BUG-37 enrichment: `harness_turn` summaries still hide meaningful grounding-path differences from humans

Additional evidence folded into `BUG-37` from `xyzgl_turn_fresh_issues_report_24 (1).md`:
- `turn_summary.md` can remain byte-identical across `DAEDALUS_GROUNDING_MODE=off` versus `DAEDALUS_GROUNDING_MODE=local` even when `turn_report.json.payload.turn_result.prompt_meta` shows materially different grounding behavior

This is the same human-readable summary blind spot already tracked in the master: the summary still flattens distinct execution paths into the same tutor-only view.

### BUG-62 enrichment: env-only mirror/privacy and prompt-path switches still change artifact semantics without being recorded

Additional evidence folded into `BUG-62`:
- `xyzgl_turn_fresh_issues_report_24 (1).md` shows grounding mode, grounding snippet cap, and protocol-path changes still altering live prompt behavior while `property_turn_fuzzer.py` artifacts remain identical
- `XYZGL_new_bug_report_round29.md` extends the same contract issue to `selfcheck.py`, which still accepts repo-style `--issue` invocation without recording or honoring the standard tool contract

These remain part of the broader artifact self-description problem already tracked in the master: env-only or prompt-path execution differences still disappear from saved tool outputs.

### BUG-81 enrichment: `reground_cadence_verifier.py` still emits non-canonical `run.json`

Additional evidence folded into `BUG-81` from `XYZGL_new_bug_report_round29.md`:
- `artifact_roundtrip.py --strict` still flags `reground_cadence_verifier.py` output because the tool manually writes `run.json` with `json.dumps(...)` instead of the canonical writer

This is the same non-canonical run-artifact family already tracked in the master.

### BUG-90 enrichment: replay still ignores more `run.json` semantic fields beyond `issue_id`

Additional evidence folded into `BUG-90` from `behavior_drift_replay_bundle_round22.zip`:
- turn-mode replay still ignores forged sibling `run.json.deterministic`
- turn-mode replay still ignores forged sibling `run.json.exit_codes`

This is the same cross-file `run.json` replay blind spot already tracked in the master, with additional semantic fields now independently confirmed.

### BUG-17 enrichment: detector coverage still misses more mirror-role phrasing and more nested text surfaces

Additional evidence folded into `BUG-17`:
- `graph_mirror_audit_round19_20260307.zip` shows `mirror_leakage_detector.py` still missing direct imperative/coaching variants such as `Always ...`, `Next, ...`, `My advice is to ...`, and French imperative phrasing (`Assure-toi de ...`)
- `behavior_drift_replay_bundle_round24.zip` shows `protocol_drift_radar.py` still ignoring `session_report.json -> turns[*].mirror.meta.error`

This remains the same detector-field-coverage blind spot already tracked in the master.

### BUG-18 enrichment: graph invariant checking still misses additional typed-value and null-drop round-trip mutations

Additional evidence folded into `BUG-18` from `graph_mirror_audit_round19_20260307.zip`:
- numeric `summary` values still pass even though runtime stringifies them on round-trip
- `required_keywords` containing `null` still pass even though runtime silently drops the null entry
- `fragility_flags` containing `null` still pass even though runtime silently drops the null entry

These are additional instances of the same checker/runtime divergence bug already tracked in the master.

### BUG-39 enrichment: `backend_contract_probe.py` still falsely fails valid non-raising fault modes under `--include-fault`

Additional evidence folded into `BUG-39` from `backend_probe_round28_new_issues_20260307.zip`:
- `DAEDALUS_FAULT_MODE=empty` with `--include-fault` still reports `expected backend to raise, but it returned normally`

This is the same non-raising-fault misclassification already tracked in the master.

### BUG-40 enrichment: malformed `--issue` acceptance still reproduces across more tools and paired backend helpers

Additional evidence folded into `BUG-40`:
- `XYZGL_new_bug_report_round31.md` reconfirms malformed `--issue` acceptance in `seed_sweep.py`, `apply_signal_fidelity_overlay.py`, `retrieval_eval_bench.py`, and `backend_fault_injector.py`
- `backend_probe_round28_new_issues_20260307.zip` independently reconfirms the same paired-tool mismatch: `backend_contract_probe.py` rejects malformed issues while `backend_fault_injector.py` still runs and writes artifacts

This is the same issue-id contract bug family already tracked in the master.

### BUG-81 enrichment: `reground_cadence_verifier.py` still emits non-canonical `run.json`

Additional evidence folded into `BUG-81` from `XYZGL_new_bug_report_round31.md`:
- `artifact_roundtrip.py --strict` still flags `reground_cadence_verifier.py` output because its `run.json` is not canonical

This is the same non-canonical run-artifact family already tracked in the master.

### BUG-90 enrichment: replay still ignores more sibling `run.json` semantics beyond `issue_id`

Additional evidence folded into `BUG-90` from `behavior_drift_replay_bundle_round24.zip`:
- sibling `run.json.deterministic` can still be forged without replay diff noticing
- sibling `run.json.exit_codes` can still be inverted without replay diff noticing

This is the same cross-file `run.json` replay blind spot already tracked in the master.

### BUG-94 enrichment: strict mismatch status inconsistency still reproduces on another producer tool

Additional evidence folded into `BUG-94` from `XYZGL_new_bug_report_round31.md`:
- `artifact_roundtrip.py --strict` still records `changed: true` with per-file `status: "PASS"` on `reground_cadence_verifier.py` output while the process exits `FAIL`

This confirms the same strict-status inconsistency bug on another concrete artifact source.

### BUG-03 enrichment: marker-like learner input still reproduces the USER-block truncation path under tight prompt budgets

- `xyzgl_new_issues_report_round27.md` reproduces the same structural prompt corruption already captured by `BUG-03`: learner input containing `<<<USER>>>`, protocol markers, or grounding markers can still consume the prompt budget in a way that preserves `<<<USER>>>` but drops `<<<END_USER>>>`, yielding the empty-input fallback reply hash.

### BUG-13 enrichment: `seed_sweep.py` artifacts still record raw user text instead of the effective sanitized routed payload

- The same round-27 report shows `seed_sweep_report.json.input` saving the pre-sanitized marker string rather than the effective routed text (`<USER_OPEN>...`, `<PROTOCOL_OPEN>...`, `<GROUNDING_OPEN>...`) that actually drove prompt construction.

### BUG-17 enrichment: `protocol_drift_radar.py` still ignores text-bearing session `user_state` fields

- `behavior_drift_replay_bundle_round26.zip` shows that role leakage placed in `turns[*].user_state` is invisible to the current radar collector even though replay-based cross-checking still detects a bundle drift. This fits the existing detector-coverage bug family in `BUG-17`.

### BUG-79 enrichment: `artifact_roundtrip.py` child-run omission remains reproducible

- `xyzgl_new_bug_report_17th_pass_2026-03-07.md` reconfirms that directory mode still uses only top-level `*.json` discovery and skips malformed nested `child_runs/**/*.json` artifacts.

### BUG-101 enrichment: `harness_session.py` still accepts semantically invalid `--protocol-reground-every 0` and emits a normal-looking PASS bundle

- The 17th-pass report confirms another variant of the broader semantic-input-validation problem already tracked by `BUG-101`: a nonsensical cadence value (`0`) is accepted, persisted into the run, and not rejected before artifact emission.

### BUG-03 enrichment: local grounding still creates additional turn-0 prompt-budget cliffs that erase or corrupt the learner block

- `xyzgl_new_issues_report_round28 (1).md` shows that with local grounding enabled, valid adjacent budgets can still truncate the prompt inside `<<<DAEDALUS_GROUNDING>>>` before any `<<<USER>>>` block is emitted, or preserve `<<<USER>>>` while dropping `<<<END_USER>>>`. This is the same prompt-boundary corruption family already tracked by `BUG-03`.

### BUG-13 enrichment: `seed_sweep.py` still reports green while adjacent valid budgets flip routed behavior for the same grounded workload

- The same round-28 report shows `seed_sweep.py` returning `PASS` while adjacent grounded turn-0 budgets flip the output among a wrong-topic fit-up correction, the empty-input fallback, and the generic fallback. This is the same false-proxy sweep bug already tracked by `BUG-13`.

### BUG-16 enrichment: strict replay still ignores forged `mirror_prediction` drift in turn bundles

- `behavior_drift_replay_bundle_round30 (1).zip` shows that `tools/repro_replay_diff.py --strict` still returns `PASS` when `turn_report.json -> turn_result.mirror_prediction` is tampered with. This is another omitted turn-level mirror provenance field within the already-tracked `BUG-16` replay-comparison blind spot.

### BUG-17 enrichment: drift detection still misses tutor-shaped mirror probes phrased as questions

- The same replay bundle shows `tools/protocol_drift_radar.py` still passing a mirror reply shaped like `Q: Can you explain your reasoning step by step?` with zero findings. This is the same detector-narrowness problem already tracked by `BUG-17`.

### BUG-27 enrichment: protocol-aware tools still fail open when the canonical `STABLE/ROLE_PROTOCOL.md` asset is missing and fallback protocol text is loaded instead

- `xyzgl_new_bug_report_20th_pass_2026-03-07.md` shows `repro_grounding_protocol_smoke.py`, `grounding_injection_audit.py`, `reground_cadence_verifier.py`, `protocol_drift_radar.py`, and `backend_contract_probe.py` all still producing normal green or nominal outputs when the canonical role protocol file is absent and only `xyzgl/protocols.py` fallback text is available. This is the same fallback-downgrade family already tracked by `BUG-27`.

### BUG-89 enrichment: grounded turn-0 behavior still collapses unrelated welding questions into the same fit-up answer when learner text is crowded out

- `xyzgl_new_issues_report_round28 (1).md` also shows an arc-length query and a fit-up query collapsing to the same fit-up correction under local grounding at a valid prompt budget. This is additional evidence for the existing topic-collapse defect tracked by `BUG-89`.

### BUG-101 enrichment: `repro_session_smoke.py` still accepts semantically invalid `--max-turns 0` and emits a normal FAIL bundle instead of rejecting input

- `xyzgl_new_bug_report_25th_pass_2026-03-07.md` shows `tools/repro_session_smoke.py --max-turns 0` allocating a run dir, emitting `session_report.json` with zero turns, and returning a semantic `FAIL` bundle instead of rejecting the configuration as invalid input. This is another instance of the broader semantic-input-validation class already tracked by `BUG-101`.

### BUG-105 enrichment: `doc_code_link_checker.py` still treats mere path existence as sufficient AI_INDEX validation

- The same report shows `tools/doc_code_link_checker.py` accepting `AI_INDEX` surfaces that resolve to a directory (`tools`) or to a non-code file (`README.md`) and still returning `PASS`. This extends the existing `BUG-105` malformed-structured-input family: the checker still does not validate that an indexed surface is a concrete code file rather than any existing repo path.

### BUG-16 enrichment: replay still ignores broken mirror paths and backend-error state

- Source: `COMBINED_BUG_REPORT_ROUND22_31_45`
- `round22_new_behavior_protocol_replay_bugs.zip` confirms turn replay does not compare `backend_error`, `mirror_prediction`, or `mirror_meta`. A turn with an enabled non-stub mirror that fails to produce a valid prediction still replays as `PASS`.

### BUG-26 enrichment: protocol_drift_radar tail-position blind spot independently confirmed with explicit role-drift payload

- Source: `COMBINED_BUG_REPORT_ROUND22_31_45`
- The same round-22 replay bundle confirms explicit tutor-role takeover text placed after character 4,000 is invisible to the radar's `_clip_text()` truncation.

### BUG-17 enrichment: protocol_drift_radar misses short imperative tutor-style mirror instructions

- Source: `COMBINED_BUG_REPORT_ROUND22_31_45`
- Short step-by-step imperative mirror text like "Stop welding now. Grind the edges flat. Re-tack at equal spacing..." does not contain the tracked lexicon (`as your tutor`, `in today's lesson`, `let's learn|practice`) and is too short for the 220-char assertive-length heuristic.

### BUG-03 enrichment: turn-0 protocol re-grounding can still crowd out or truncate the final USER block on the plain path

- Source: `COMBINED_BUG_REPORT_ROUND22_31_45`
- `xyzgl_new_issues_report_round31.md` shows turn-0-only protocol payload consuming prompt budget before the mandatory USER block at lower valid `max_chars_in` values (1900???2000 range), producing generic fallback or empty-input fallback, while the same budget on turn 1 (which skips protocol re-grounding) produces the correct answer.

### BUG-107 enrichment: secret_scanner still misses broader real-world credential labels including camelCase, OAuth-style, and service-account variants

- Source: `COMBINED_BUG_REPORT_ROUND22_31_45`
- `XYZGL_new_bug_report_round45.md` confirms enforce-mode false negatives for `clientKey=...`, `consumer_key=...`, `consumer_secret=...`, `service_account_key=...`, and `session-key: ...`. The generic assignment regex still only matches a narrow field-name family.


## Appendix A ???????? Issues Resolved in Round 33

These were fixed by Round 33 patches and are **not** part of the open defect list.

### RESOLVED-R33-A: `util_http.py` retried all `URLError` failures unconditionally

- **Fix applied:** `_is_transient_error()` now inspects `URLError.reason`; only transient errors are retryable.

### RESOLVED-R33-B: Oversized input could cause unbounded NFC normalization work

- **Fix applied:** `_normalize_input_text_bounded()` pre-caps raw input before NFC normalization.

### RESOLVED-R33-C: Distribution package included transient runtime artifacts

- **Fix applied:** Rebuilt from clean tree excluding `runs/`, `tmp_*`, `__pycache__/`, `*.pyc`, `*.pyo`.

---

## Appendix B ???????? Bundles Triaged With No Additional Defects

- `memory_audit_report_patch_round51.zip` ???????? references modules that do not exist.
- `XYZGL_round36_bug_report_bundle.zip` ???????? reported zero issues.
- Several bundles included diffs targeting nonexistent files (`api_routes.py`, `retry_handler.py`, etc.). The one concrete match (retry classification) is RESOLVED-R33-A.

---

## Appendix C ???????? Deduplication Map

Thirty-six overlaps were identified across the original seven source reports that produced the v4 master.

### From the first three reports (5 merges):

| Unified ID | Source 1 | Source 2 | Source 3 | Merge reason |
|------------|----------|----------|----------|--------------|
| BUG-01 | R21-R33 BUG-01 | Replay BUG-03 | ???????? | Identical `_is_real_tutor_backend()` pattern |
| BUG-12 | R21-R33 BUG-07 | R3 BUG-03 | ???????? | Both about simulated learner being too simplistic |
| BUG-13 | R21-R33 BUG-08 | R3 BUG-04 | ???????? | Both about nondeterministic artifacts + false proxy |
| BUG-17 | Replay BUG-05 | R3 BUG-06 | R3 BUG-08 | All about narrow mirror/drift detection |
| BUG-18 | Replay BUG-06 | R3 BUG-07 | ???????? | Same graph checker tool, same issues |

### From Round 4 integration (9 merges):

| Unified ID | Round 4 Source | Merge type | Reason |
|------------|---------------|------------|--------|
| BUG-10 | R4 BUG-01 | Enriched | Adds lone-surrogate Unicode crash vector |
| BUG-16 | R4 BUG-05 | Enriched | Adds backend provenance fields missing from `--strict` |
| BUG-14 | R4 BUG-06 | Exact dup | Same replay parsing inconsistency |
| BUG-18 | R4 BUG-08 | Enriched | Adds `summary`, `fragility_flags`, numeric-string coercion |
| BUG-17 | R4 BUG-09 | Enriched | Adds zero-width obfuscation, imperative starters |
| BUG-05+06 | R4 BUG-10 | Covered | Redacted-mode delimiter injection covered by BUG-05 + BUG-06 |
| BUG-03 | R4 BUG-11 | Enriched | Adds half-open grounding structural marker |
| BUG-22 | R4 BUG-16 | Exact dup | Same stale mutation suite patterns |
| ???????? | R4 triage note | Subsumed | Contract probe gap subsumed by BUG-22 |

### From Round 6 integration (7 merges):

| Unified ID | Round 6 Source | Merge type | Reason |
|------------|---------------|------------|--------|
| BUG-13 | R6 F-003 | Enriched | Adds tutor-fallback masking in seed_sweep |
| BUG-13 | R6 F-004 | Enriched | Adds mirror-failure masking in seed_sweep |
| BUG-13 | R6 F-005 | Enriched | Adds strict-mode unstructured crash in seed_sweep |
| BUG-20 | R6 F-010 | Confirmed dup | Same absolute-path grounding bypass |
| BUG-02 | R6 F-012 | Enriched | Adds fault/empty mode evidence |
| BUG-02 | R6 F-013 | Enriched | Extends empty-reply blind spot to teach-phase |
| BUG-30 | R6 F-014 | Enriched | Adds tutor-empty to missing fault injector scenarios |

### From Round 7/8/9 and Targeted Sweep integration (15 merges):

Cross-duplicates between the two new reports (6 pairs):

| Report A | Report B | Merge reason |
|----------|----------|--------------|
| A-01 | B-F006 | Same: malformed issue IDs |
| A-02 | B-F007 | Same: latency enforcer not hermetic |
| A-03 | B-F008 | Same: grounding audit env-sensitive |
| A-07 | B-F001 | Same: harness session green-only |
| A-08 | B-F002 + B-F003 | Same: seed_sweep raw input + Unicode drift |
| A-09 | B-F004 + B-F005 | Same: seed_sweep empty PASS + orphan dirs |

Merges into existing v3 bugs (9):

| Unified ID | Source | Merge type | Reason |
|------------|--------|------------|--------|
| BUG-07 | A-07/B-F001 | Enriched | Adds harness green-only / post-mastery overrun angle |
| BUG-13 | A-08/B-F002+F003 | Enriched | Adds raw-input artifact mismatch and Unicode-equivalence drift |
| BUG-13 | A-09/B-F004+F005 | Enriched | Adds all-empty PASS confirmation and orphan empty dirs |
| BUG-25 | A-05 | Enriched | Adds degraded-path metadata and empty-reply false-pass |
| BUG-29 | A-10 | Exact dup | Same: contract probe accepts empty output |
| BUG-30 | A-11 | Enriched | Adds `effective_backend` switch assertion |
| BUG-17 | B-F012 | Enriched | Adds eval/session mirror answer blind spot |
| BUG-29 | B-F004 (empty) | Subsumed | All-empty PASS subsumed into BUG-13 sweep coverage |
| ???????? | A-12 patch context | Noted | Round-25 targeted_sweep rewrite is patch context, not a bug |

### From Standalone Combined Reports (12 enrichments + 18 new):

| Combined Report Finding | Disposition | Target |
|------------------------|-------------|--------|
| R9/10/11/13 BUG-03 | Enriched | BUG-03 (sanitization expansion angle) |
| R9/10/11/13 BUG-04 | Enriched | BUG-18 (size/budget checks) |
| R9/10/11/13 BUG-05 | Enriched | BUG-17 (tutor-role phrasing) |
| R9/10/11/13 BUG-08 | Enriched | BUG-21 (query-window + tie-win + flooding) |
| R8/9/10/25/26 BUG-07 | Enriched | BUG-32/33/50 (session env toggles) |
| R8/9/10/25/26 BUG-11 | Duplicate | BUG-45 (targeted_sweep scrubs stdout) |
| R8/9/10/25/26 BUG-12????????14 | Enriched | BUG-21 (retrieval tie/diversity/query) |
| R10/11/12/14 BUG-01 | Enriched | BUG-25 (fuzzer can't distinguish behavior) |
| R10/11/12/14 BUG-05 | Enriched | BUG-19 (overlong source_id starves prompt) |
| R10/11/12/14 BUG-06 | Enriched | BUG-20 (redteam PASS without grounding) |
| R10/11/12/14 BUG-08 | Enriched | BUG-18 (graph checker bounds) |
| R10/11/12/14 BUG-10 | Enriched | BUG-17 (imperative phrasing) |

---

## Appendix D ???????? Out-of-Scope Items

### CompanionWriter Prompt-Audit Bundles

The following bundles are prompt-audit / prompt-fix artifacts for the `CompanionWriter_Sovereign_Apex` prompt family rather than XYZGL runtime, harness, detection, or grounding code. They are not counted in the XYZGL defect total.

- `CompanionWriter_Sovereign_Apex_v11_bundle (2).zip` ???????? 4 prompt-logic fixes (parsing ambiguity, overbroad instruction gates, calibration contradiction, blocker-format ambiguity)
- `CompanionWriter_Sovereign_Apex_v11_1_bugfix_bundle.zip` ???????? 5 prompt-structure / command-policy issues
- `CompanionWriter_Sovereign_Apex_v11_2_bugfix_bundle.zip` ???????? 2 prompt determinism / phase-definition issues
- `CompanionWriter_Sovereign_Apex_v11_3_bugfix_bundle.zip` ???????? 2 XML/policy-duplication issues
- `CompanionWriter_Sovereign_Apex_v11_6_bugfix_bundle.zip` ???????? 8 prompt-structure / XML / command-palette issues

### Patch-Only Context

- `round26_targeted_sweep_artifact_isolation_patch (3).zip` ???????? treated as patch context, maps to existing BUG-45 and sweep isolation hardening; not a separate defect.

### Workflow Prompt Lists

- `xyzgl_bug_tool_workflows_10_prompts.txt` ???????? workflow prompt list for bug-hunting passes; no direct defect findings.

---

## Acceptance Criteria (All 73 Open Bugs)

1. Non-strict tutor config/runtime faults fall back to stub in both router and orchestrator flows.
2. Final replies are never empty in non-strict mode and always preserve the `Safety first: ` prefix. Empty tutor replies trigger backend failure in both router and teach-phase paths. Strict mode raises on empty contract results.
3. Prompt-budget pressure cannot remove the final user block or leave half-open structural markers. Budget cap is applied after sanitization.
4. Stub mirror replies are learner-shaped and no longer wrap tutor instructions.
5. Mirror redaction mode never includes learner/tutor content excerpts.
6. Mirror prompt boundaries cannot be injected by user content in any mode.
7. Protocol-load failures are surfaced explicitly; fallback downgrades are never reported as successful regrounding.
8. Empty mirror backend outputs are treated as backend failures in both router and orchestrator flows.
9. Empty tutor output in probe/eval phases is treated as backend contract failure in both strict and non-strict modes.
10. Session runs terminate immediately when all nodes are mastered. The harness distinguishes completion from overrun.
11. Different seeds produce different eligible node orders without deterministic starvation.
12. Session runs preserve inferred learner state and pointed probe intent across turns.
13. `harness_turn` always emits artifacts (including on failures and invalid Unicode) and those artifacts redact sensitive input.
14. Turn artifacts clearly distinguish raw input, normalized input, and the final prompt-facing user block.
15. `turn_summary.md` is faithful, control-character safe, size-bounded, and includes mirror output when present.
16. Session harnesses deterministically exercise PROBE before CLOSE_NODE on the first pass.
17. Simulated learner responses depend on the actual tutor question and prior attempts.
18. Deterministic harness re-runs produce byte-stable artifacts with stable IDs and timestamps.
19. Seed sweep validates live session behavior, surfaces backend fallback and mirror failures, produces structured results in strict mode, rejects empty replies, and records canonical routed input.
20. `harness_session` respects env-backed protocol reground cadence, protocol path, and grounding directory.
21. Harness isolation flags are either honored by runtime code or removed.
22. `harness_turn` treats empty tutor reply as failure, not PASS.
23. Mirror enablement and privacy controls are propagated and auditable across session tooling.
24. Seed sweep run identity is workload-derived, not seed-derived, and collision resolution propagates to all artifacts.
25. Run paths are anchored to the repository, not to the shell CWD.
26. Invalid DAEDALUS_RUNS_DIR overrides fail loudly, not silently.
27. Dead CLI flags are either implemented or removed.
28. Harness artifacts capture env-only behavior switches and fault-injection controls needed for replay.
29. Replay uses the same node-identification logic as the original session harness.
30. `repro_replay_diff` checks both turn and session artifacts when both are present.
31. Replay diffing flags turn-level mirror drift, fallback drift, and backend provenance drift.
32. Replay validates bundle consistency across multi-file artifacts (turn_summary.md, knowledge_graph.json).
33. `targeted_sweep` succeeds or fails based on artifact content, not missing flags, and correctly recovers child run paths.
34. `targeted_sweep` does not self-contaminate the `doctor` check.
35. Mirror-leakage and protocol-drift tools flag obvious tutor-style language after normalization, scan mirror answers in eval/session data, scan `eval.next_action`, scan `session_summary.md`, and fail on mirror role confusion.
36. Mirror leakage detector requires valid report/session schema, not arbitrary JSON.
37. Protocol drift scanning catches phrases regardless of text position.
38. Graph invariant checking rejects malformed JSON, missing `summary`, wrong types, boolean-for-integer, stringified numerics, and graph-core boundedness violations.
39. `property_turn_fuzzer` fails on backend provenance regressions and empty replies, preserves failing testcase inputs, writes canonical `run.json`, reaches welding-specific branches, generates control/Unicode stressors, reports effective coverage accurately, and emits one stable report schema across all exit paths with explicit dropped-evidence counts.
40. `backend_contract_probe` rejects empty backend output, does not falsely fail supported non-raising fault modes, cannot report PASS with zero probes, rejects boolean latency_ms, and validates backend identity.
41. `backend_fault_injector` verifies fallback/error invariants and covers both mirror-empty and tutor-empty scenarios.
42. `prompt_snapshot_guard` does not self-seed baselines without `--update`.
43. Every issue-scoped tool rejects malformed `ISSUE-YYYYMMDD-NNN` values before doing work.
44. Deterministic audit and budget tools are hermetic under ambient backend and grounding env contamination.
45. `secret_scanner` cannot silently pass over large text blobs.
46. Tool documentation matches actual tool outputs.
47. Oversized grounding candidates are skipped instead of starving later snippets. Overlong source identifiers are bounded.
48. Oversized manifests produce explicit errors, not silent degradation.
49. Invalid grounding paths cannot report `grounding_enabled=True` unless grounding actually loaded. RAG poisoning suite fails when grounding is expected but absent.
50. Grounding corpus prevents duplicate source aliases, lexical tie bias, single-source domination, keyword-stuffing attacks, and query-window truncation abuse.
51. Source and passage caps cannot silently suppress relevant content without surfacing warnings.
52. Duplicate root keys in `manifest.json` produce explicit errors.
53. Grounding audits detect and fail when grounding is configured as enabled but no snippets were produced.
54. Grounding headers cannot be forged by raw manifest ids or titles.
55. Retrieval bench corpus validation matches runtime grounding validation.
56. Chunk splitting does not create retrieval failures at passage boundaries.
57. Selfcheck and mutation testing cover the fixed behavior with patterns that match actual source code.














