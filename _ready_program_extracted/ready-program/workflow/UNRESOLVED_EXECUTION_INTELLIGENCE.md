# Unresolved Execution Intelligence

This file is the strategy layer for the remaining backlog.
Use it together with:

1. `workflow/STATUS.md`
2. `workflow/config/windows.json`
3. your window queue file
4. `workflow/scripts/get_bug_section.ps1 -BugId BUG-XXX`

Rules:

- Treat the queue and getter output as the legal selector.
- Treat the bug section, the queue doctrine, and this file as the implementation bar.
- Prefer robust contract fixes over narrow symptom masking.
- Keep changes replayable, deterministic, auditable, and honest about what was truly exercised.
- If a bug touches certification, coverage, or evaluation truth, fail closed rather than emitting a flattering green result.

## Window 01

- `BUG-27`: Fail closed on invalid protocol paths. The resulting error surface should be stable enough for operators and support tooling to identify misconfiguration without replaying the run.
- `BUG-54`: Reject empty tutor output at the parsing boundary. Preserve structured failure detail so blank-model incidents are distinguishable from downstream parser failures in production telemetry.
- `BUG-83`: Enforce semantic validation on backend metadata even when no exception is raised. Make the invalid field and verdict visible enough that enterprise support can remediate configuration issues quickly.
- `BUG-103`: Normalize or reject non-UTF-8-safe backend strings before witness and artifact code use them. The runtime and probe tooling must share one certification-grade validation contract.

## Window 02

- `BUG-80`: Preserve paragraph boundaries in grounding corpora even when separators are whitespace-only. Keep the rule portable so customer corpora behave consistently across authoring environments.
- `BUG-92`: Normalize manifest source paths across Windows and POSIX separators. The path contract should be deterministic enough for packaged curriculum assets and user-supplied corpora to round-trip cleanly.
- `BUG-102`: Remove the hidden `grounding_max_snippets` re-clamp. Operators need one trustworthy knob for grounding spend, latency, and answer richness.

## Window 03

- `BUG-70`: Repair passage-boundary chunk splitting so evidence at chunk edges stays retrievable. Preserve deterministic chunk identities so benchmark baselines remain saleable and stable.
- `BUG-93`: Make shown retrieval excerpts include the actual matching evidence. The displayed snippet should be customer-review-grade proof, not a cosmetically plausible paraphrase.
- `BUG-99`: Validate benchmark row field types before evaluation trusts them. Replace false passes and late crashes with crisp contract failures that make external benchmark packs safe to automate.

## Window 04

- `BUG-09`: Preserve conversational continuity across turns in the session orchestrator. The continuity must be strong enough to support trustworthy longitudinal tutoring features and customer-facing session exports.

## Window 06

- `BUG-50`: Propagate mirror enablement and privacy controls through session tooling and exported artifacts. Treat those controls as paid trust features whose effective state must stay inspectable end to end.
- `BUG-52`: Make sweep run identity depend on the actual workload, not only the seed integer. Stable but truthful identity makes dashboards, reports, and support escalations materially more useful.
- `BUG-55`: Resolve run roots against a stable tool contract instead of caller cwd. The path behavior should be reliable enough for CI, scheduled jobs, and customer-hosted automation.
- `BUG-82`: Report the real learner state and active tutoring branch in session artifacts. The exported story should be accurate enough to power analytics, instructor review, and customer success workflows.

## Window 07

- `BUG-90`: Compare cross-file `issue_id` identity inside replay bundles. A green replay result should be credible enough for paid support and regression review workflows.
- `BUG-104`: Inspect nested `payload.session_report.schema_version` fields, not only top-level filenames. Surface semantic drift early so downstream consumers do not discover incompatibilities after shipment.

## Window 08

- `BUG-45`: Separate run-path extraction from cosmetic child-output sanitization. Keep the audit breadcrumb while still meeting production logging hygiene.
- `BUG-67`: Run repo health checks before sweep code dirties the working tree. The tool should be safe in premium CI and customer demo environments where false repo dirtiness destroys confidence.

## Window 09

- `BUG-113`: Bind smoke artifact names and schema versions to the tool that emitted them. Each report should be trustworthy enough to feed billing, compliance, and support pipelines without relabeling.
- `BUG-76`: Extract the child run dir before sanitizing child stdout. CI failures should remain self-serve so a paying team can inspect the exact bundle without rerunning the job.

## Window 10

- `BUG-79`: Treat nested `child_runs/**/*.json` files as first-class roundtrip targets. Nested artifacts are sellable evidence, not optional debris.
- `BUG-94`: Keep strict-mode process verdicts aligned with per-file verdicts. A premium strict report must read like one coherent judgment instead of a contradiction that forces manual arbitration.

## Window 11

- `BUG-42`: Isolate environment sensitivity in `grounding_injection_audit.py`. Deterministic audit behavior is what turns the tool into a customer-facing assurance check instead of an internal helper.
- `BUG-53`: Ship or regenerate the required companion docs for `signal_fidelity_port.py`. Treat the docs as part of the feature so operators can adopt it without reading source.
- `BUG-77`: Remove the nonexistent default overlay archive. First-run success matters if the tool is going to feel productized rather than hand-held.

## Window 12

- `BUG-64`: Stop silently skipping large text files in `secret_scanner.py`. Large-corpus trust is part of the commercial value proposition, so the scanner must never fail open on the files customers care about most.
- `BUG-73`: Include `session_summary.md` in directory scans for `protocol_drift_radar.py`. Expand the scan so the summary surface becomes a dependable review artifact rather than a blind spot.

## Window 13

- `BUG-91`: Treat stdout/stderr side effects as part of backend validation truth. Side-effect truthfulness is what keeps backend certification credible in regulated and customer-hosted environments.
- `BUG-97`: Run the no-network gate before backend construction. Clean defect classification makes the probe easier to support and keeps offline SKUs from looking broken for the wrong reason.

## Window 14

- `BUG-34`: Emit canonical `run.json` artifacts from `property_turn_fuzzer.py`. The bundle should be good enough to flow through the same tooling and paid assurance workflows as any other run.
- `BUG-35`: Reach the welding-specific single-turn branch from the fuzzer. Coverage proof should map directly to the product branch customers are buying, not a generic harness story.
- `BUG-36`: Generate the missing control and Unicode stressors. This hardens the tutor for messy real-world inputs common in international and enterprise deployments.
- `BUG-44`: Preserve canonical schema and failing evidence on incomplete paths. Failed paths should still produce support-ready artifacts instead of expensive dead ends.
- `BUG-63`: Bring `ai_property_turn_fuzzer.md` back into sync with real tool output. The documentation should be good enough to sell and onboard the feature without side-channel explanation.
- `BUG-68`: Stop overstating coverage when `--max-len=0`. Honest coverage claims are part of the product's credibility when artifacts are shown to customers or auditors.

## Window 15

- `BUG-96`: Require lattice sweeps to prove meaningful semantic movement. Turn the suite into a decision-grade benchmark that can justify tuning and premium quality claims.
- `BUG-98`: Reject malformed structured prompt layouts in `redteam_rag_poisoning_suite.py`. The suite should behave like a hard security product, not a permissive demo.

## Compiler Guidance

- Window `16`: runtime side only. Favor semantic merge correctness over preserving source-window ordering when the patches disagree.
- Window `17`: tooling side only. Favor canonical artifact contracts, docs, and guardrail strictness over permissive merges.
- Window `18`: final integration only. It must publish both the ready-program artifact and backward-sync patch every cycle close.
