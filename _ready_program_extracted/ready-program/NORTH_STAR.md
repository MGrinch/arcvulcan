# NORTH STAR - ARCVULCAN (XYZGL ENGINE)

> Name history: Project Daedalus / XYZGL -> AegisForge -> AnvilMind -> AegisAnvil Vigil -> ArcNebula Forge -> QuasarArc Foundry -> PulsarArc Forge -> SupernovaArc Forge -> MagnetarArc Forge -> AnvilEmpyrean -> ForgeSeraph -> CrucibleGenesis -> AnvilEschaton -> FluxFirmament -> QuenchHalo -> ForgeEmpyrean -> CrucibleSeraph -> AnvilHalo -> FluxCovenant -> ArcSanctum -> ForgeRevelation -> ArcVulcan. Internal module remains `xyzgl` -> ArcVulcan (current).

ArcVulcan (XYZGL) is a deterministic, inspectable tutoring system for Ontario welding.
It exists to make teaching decisions replayable, auditable, and progressively better without unbounded agency.

This North Star is the beacon: if a change breaks these principles, it is off-mission.

## Purpose

ArcVulcan must:

1. Diagnose the learner's knowledge graph: nodes, gaps, fragility.
2. Select the optimal next target using signals, not vibes.
3. Deliver cognitively-budgeted instruction matched to learner state.
4. Probe reasoning until bedrock logic is reached.
5. Update the graph deterministically and repeat.

## Canonical Roles

### 1. Orchestrator (XYZGL)

Routes turns, enforces protocol, captures telemetry, and writes audit artifacts.

### 2. External Tutor (fast API model)

Performs curriculum selection, instruction synthesis, and reasoning audits.
It must be grounded in:

- rules of engagement (protocol-first)
- Ontario welding standards and texts

### 3. Local Mirror (deterministic local model)

Simulates the user: predicts likely answers under a given state. It does not teach.
It improves only via corrective deltas from the Tutor.

## Protocol-First Rules

1. Protocol precedes knowledge grounding.
2. Each role speaks only when invoked by the Orchestrator.
3. No cross-role improvisation.
4. Protocols are re-grounded periodically to prevent drift.
5. Outputs must be schema-valid and auditable.

Protocol source of truth: `STABLE/ROLE_PROTOCOL.md`.
System constraints source of truth: `STABLE/WITNESS_PROTOCOL_v2.1.md`.

## Canonical Learning Cycle

1. Boot and handshake: load Local Mirror, connect Tutor, reground protocol.
2. State intake: prompt user, capture text plus telemetry, infer state (`FLOW` or `FRUSTRATED`).
3. Target selection: choose the next node from the knowledge graph.
4. Instruction synthesis:
   - `FLOW`: higher density (10-15 sentences)
   - `FRUSTRATED`: lower density (7-10 sentences)
5. Mirror simulation: Mirror predicts the likely user answer.
6. User response: the user answers and telemetry is captured.
7. Comparison and correction: Tutor compares user vs Mirror and issues corrections.
8. Reasoning probes: pointed Q/A mini-cycles until bedrock logic is reached.
9. Graph update: update node mastery and fragility.
10. Repeat.

## Determinism And Verification

If `--seed` is provided, outputs must be stable for the same `(seed, input)`.
Every run must produce auditable artifacts validated by JSON Schemas:

- `runs/<run_id>/turn_report.json`
- `runs/<run_id>/lattice_report.json` when applicable
- `runs/<run_id>/run.json`

Primary tools:

- `tools/harness_turn.py`
- `tools/harness_lattice.py`
- `tools/validate_schemas.py`
- `tools/doctor.py`

## Current Implementation State

This repo is intentionally runnable without network calls.
The "Tutor" is currently a deterministic local stub in `xyzgl/welding_tutor.py` so the harnesses can verify determinism and schema stability.

Replacing the stub with real backends (Ollama plus external API) must preserve:

- the safety prefix invariant
- deterministic behavior when seeded
- the Witness Protocol workflow

## Directory Anchors

- `00_NAVIGATOR_DRIVER_START_HERE.md` - first steps
- `STABLE/WORKFLOW_ASSISTANT.md` - how we work (repro-first)
- `STABLE/WITNESS_PROTOCOL_v2.1.md` - immutable laws
- `STABLE/SPEC_v3.0.2.md` - interfaces and invariants
- `docs/AI_INDEX.json` - surface and contract map
- `docs/DEPENDENCY_GRAPH.json` - dependency topology

## Development Beacon

Prefer replayable, deterministic, inspectable behavior over opaque convenience.
If a change makes the system harder to audit, harder to replay, or harder to reason about, it is moving in the wrong direction.
