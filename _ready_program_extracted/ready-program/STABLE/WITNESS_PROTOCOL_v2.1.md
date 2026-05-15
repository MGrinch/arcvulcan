# WITNESS_PROTOCOL v2.1 (STABLE)

This repo follows a **repro-first** workflow. We do not “fix by vibe”.
Every fix must be tied to a deterministic reproduction (an ISSUE and a harness run).

## The 6 Immutable Laws

1) **No fix without a failing repro**
   - If we can’t reproduce it deterministically, we don’t claim a fix.

2) **No runtime-state serialization**
   - Don’t “save the world” from a live process to make a test pass.
   - Prefer minimal inputs and explicit fixtures.

3) **No symptom suppression**
   - Don’t hide errors with broad try/except, silent retries, or “if error: return ok”.
   - Convert unknowns into explicit failure modes.

4) **No unverified dependencies**
   - If you add a dependency, justify it and verify it (pin versions if needed).

5) **No unbounded agency**
   - Tools do not perform external actions without explicit user command.
   - No autonomous browsing, emailing, writing files outside the repo, etc.

6) **No “fixed” claims without tests + blast radius**
   - Run the repro harness + relevant selfchecks.
   - Report what changed and what might be impacted.

## Workflow Phases

### 1) Scout
- Understand symptom and environment.
- Identify the smallest possible reproduction surface.

### 2) Witness
- Encode the failing repro into a **harness** run:
  - `tools/harness_turn.py` for a single turn
  - `tools/harness_lattice.py` for stability grid runs
- Record as an `ISSUE-YYYYMMDD-NNN` entry in `STABLE/docs/KNOWN_ISSUES.md`.

### 3) Judge
- Propose the minimal change that fixes the repro.
- Explicitly list:
  - Contract changes
  - Dependencies
  - Failure modes / sharp edges

### 4) Auditor
- Re-run the repro harness.
- Validate schemas.
- Summarize blast radius:
  - what files changed
  - which contracts were touched
  - which harnesses passed

## Determinism Policy (Practical)

- If `--seed` is provided, outputs must be stable for the same `(seed, input)`.
- Harnesses must not depend on clock time for functional output (run_id may).
- Avoid hidden global randomness.

