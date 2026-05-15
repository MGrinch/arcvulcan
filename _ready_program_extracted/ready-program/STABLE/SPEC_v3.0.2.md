# SPEC v3.0.2 (STABLE)

> Patch note (2026-01-29): harness_lattice risk scoring + schemas added; spec text refreshed.

> Project name (2026-02-03): **ArcVulcan** (XYZGL engine).


## Purpose
XYZGL routes user input to an LLM safely and predictably, and formats the response as a welding tutor.

This repo defaults to a **local deterministic stub** (no network calls)
so the debug harnesses are reproducible.

Real backends (opt-in):
- Tutor: Gemini (external)
- Mirror: Ollama (local)

See `documentation/backends/ai_backends.txt`.

## Invariants
- No unbounded agency.
- No mutation of user files unless explicitly commanded.
- Deterministic behavior when `--seed` is provided **for stub backends**.
  (Hosted models are best-effort even with temperature=0.)
- Safety-first response prefix is preserved: `Safety first: ...`

## Interfaces
- `xyzgl.router.route_turn(user_text, *, seed=None, cfg=None) -> dict`
- `xyzgl.welding_tutor.tutor_reply(user_text, *, seed=None) -> str`

## Harnesses (Testing hooks)
- `tools/harness_turn.py`
  - single end-to-end turn run
  - writes `turn_report.json`, `turn_summary.md`, `run.json`
- `tools/harness_lattice.py`
  - grid run across (seed, process, thickness, defect)
  - adds risk scoring + failure bucketing
  - writes `lattice_report.json`, `lattice_summary.md`, `run.json`
- `tools/validate_schemas.py`
  - validates harness outputs using JSON Schemas under `schemas/`
- `tools/doctor.py`
  - repo sanity checks (required files, no pycache, line budget, imports)

## Failure modes
- Non-deterministic outputs (seed not applied)
- Unhandled exceptions in routing
- Harness outputs drift from expected JSON structure

## Schema policy
All harness JSON outputs must validate against:
- `schemas/turn_report.schema.json`
- `schemas/lattice_report.schema.json`
- `schemas/run_meta.schema.json`
