# WORKFLOW_ASSISTANT (STABLE)

Canonical workflow for an assistant/contributor working inside **ArcVulcan / XYZGL**.

Non-negotiables:
- Deterministic, auditable changes (repro-first).
- Protocol-first behavior.
- 1:1 code ↔ docs.
- Obey the repo line budget enforced by `tools/doctor.py`.

---

## 0) Always-ground sequence (do this first)

1) Repo sanity:
```bash
python tools/doctor.py
```

2) Read in order (do not skip):
- `00_NAVIGATOR_DRIVER_START_HERE.md`
- `NORTH_STAR.md`
- `STABLE/ROLE_PROTOCOL.md`
- `STABLE/WITNESS_PROTOCOL_v2.1.md`
- `STABLE/SPEC_v3.0.2.md`

3) Load the system map:
- `docs/AI_INDEX.json`
- `docs/DEPENDENCY_GRAPH.json`

4) Choose mode:
- **Answer-only** (explain/plan)
- **Repo-change** (edit files)

---

## 1) Modes

### A) Answer-only
Use when the user wants explanation, planning, or review.

Rules:
- No file edits.
- No “implemented/fixed” claims.
- If a claim depends on runtime behavior, prefer running harnesses.

### B) Repo-change
Use when the user asks you to implement/refactor/add schemas/docs.

Rules:
- Follow **Witness Protocol v2.1** phases.
- Minimal change, contract-first.
- No unbounded agency (no browsing/actions without explicit user command).

---

## 2) Witness Protocol v2.1 (how to change anything)

Source of truth: `STABLE/WITNESS_PROTOCOL_v2.1.md`.

### Phase 1 — Scout
Goal: reduce ambiguity, identify the smallest surface.

Checklist:
- Identify target surface: `xyzgl/`, `witness/`, or `tools/`.
- Confirm the surface contract in `docs/AI_INDEX.json`.
- Confirm import edges in `docs/DEPENDENCY_GRAPH.json`.
- List the invariants you must not break (see §3).

### Phase 2 — Witness
Goal: capture a deterministic reproduction.

Steps:
1) Create/choose an issue id: `ISSUE-YYYYMMDD-NNN`.
2) Record repro in `STABLE/docs/KNOWN_ISSUES.md`.
3) Run the harness:

Single turn:
```bash
python tools/harness_turn.py --issue ISSUE-YYYYMMDD-NNN --seed 1337 --text "..."
```

Stability grid:
```bash
python tools/harness_lattice.py --issue ISSUE-YYYYMMDD-NNN
```

4) Validate JSON outputs:
```bash
python tools/validate_schemas.py runs/<run_id>/
```

Do not “fix” until the repro is recorded.

### Phase 3 — Judge
Goal: propose the smallest change that fixes the repro.

Rules:
- Prefer minimal edits over refactors.
- No symptom suppression (no broad try/except, silent retries).
- No runtime-state serialization.
- No unverified dependencies (justify/verify; pin if needed).
- Update docs 1:1 (see §4).
- If a file exceeds the line budget, split it (see §5).

### Phase 4 — Auditor
Goal: prove the change worked.

Steps:
- Re-run the same harness with the same `(seed, text)`.
- Re-run `tools/validate_schemas.py`.
- Write blast radius: files changed, contracts touched, sharp edges.
- Update `STABLE/docs/KNOWN_ISSUES.md` with the outcome.

Never claim “fixed” without a passing repro harness + blast radius note.

---

## 3) Core invariants (do not break)

From `STABLE/SPEC_v3.0.2.md` and current harness checks:
- Offline by default: harness paths must not require network.
- Grounding/backends are opt-in via env/CLI (keep default stub + no grounding).
- Reply prefix: `Safety first:`
- Determinism: same `(seed, input)` ⇒ same reply **for stub backends**; real APIs are best-effort.
- Input bounds: `max_chars_in` / `max_chars_out` enforced in routing.
- No unbounded agency (external actions require explicit command).
- PII hygiene: `witness/core.py` scrubs common sensitive keys.

---

## 4) 1:1 code ↔ docs rule (mandatory)

If you change code behavior or outputs:
1) Update the nearest canonical doc:
   - STABLE docs for invariants/spec/workflow
   - tool docs under `documentation/tools/`
2) Update the map if needed:
   - New “surface” ⇒ add to `docs/AI_INDEX.json`
   - New dependency edge ⇒ update `docs/DEPENDENCY_GRAPH.json`
3) If JSON output shape changes:
   - Update schemas in `schemas/`
   - Validate via `tools/validate_schemas.py`

Note: `runs/` is generated output, never source of truth.

---

## 5) Line budget and splitting

`tools/doctor.py` currently enforces `MAX_LINES = 200` for `.py`, `.md`, `.txt`.

If a file exceeds budget:
- Split by single-responsibility boundaries.
- Prefer helper modules like `tools/<tool>_lib.py`.
- Update imports, doc references, AI_INDEX, and dependency graph.

---

## 6) Repo hygiene

- Never commit `__pycache__/` or `*.pyc`.
- Do not write outside repo root.
- Treat `runs/` as ephemeral.

---

## 7) Overlay handling (Signal Fidelity drop)

If you are given Signal Fidelity files under `signal_fidelity_src/` or via
`tools/apply_signal_fidelity_overlay.py --overlay ...`:
- Do **not** auto-merge them.
- Only extract/merge with explicit user instruction.
- Prefer staged merge: extract → diff → merge in repro-backed steps.

---

## 8) Standard commands (copy/paste)

```bash
python tools/doctor.py

python -m xyzgl.cli --seed 123 How do I prep for SMAW 2F?

python tools/harness_turn.py --issue ISSUE-YYYYMMDD-NNN --seed 1337 --text "..."
python tools/harness_lattice.py --issue ISSUE-YYYYMMDD-NNN

python tools/validate_schemas.py runs/<run_id>/
```
