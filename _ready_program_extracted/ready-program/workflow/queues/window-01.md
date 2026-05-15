# Window 01 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - STABLE/WITNESS_PROTOCOL_v2.1.md
  - xyzgl/router.py
  - xyzgl/orchestrator/tutor_phases.py

- Delivery standard:
  - Reject malformed or semantically invalid runtime inputs explicitly.
  - Preserve replayability and UTF-8-safe artifact emission.
  - Add regression coverage at the entry point that previously fail-opened.

1. BUG-27 | phase 1 | High | Invalid protocol paths silently downgrade to the fallback protocol
   files: xyzgl/prompting.py, xyzgl/protocols.py
   mission: Turn invalid protocol paths into explicit, auditable failure handling instead of a silent downgrade. Emit a stable reason code or artifact signal so hosted support and compliance tooling can classify the fault without manual log digging.
   acceptance: An invalid configured protocol path does not quietly select fallback protocol content. | Regression proves the emitted error or fallback path is deterministic and inspectable.
   nexus: Validate configured protocol path existence and readability before fallback selection. | Keep any permissive fallback behind an explicit policy branch with a test.

2. BUG-54 | phase 1 | High | Empty tutor output is silently accepted in `run_probe_phase()` and `run_eval_phase()`
   files: xyzgl/orchestrator/parsing.py, xyzgl/orchestrator/tutor_phases.py
   mission: Reject empty tutor output before later phases normalize it into a fake success. Preserve enough structured context that premium monitoring can distinguish model blanking from downstream parser or transport failures.
   acceptance: Probe and eval phases both fail closed on empty tutor output. | Tests assert no downstream PASS artifact is emitted from empty model output.
   nexus: Treat blank or whitespace-only tutor output as invalid at the parsing boundary. | Propagate a structured failure that preserves debugging context.

3. BUG-83 | phase 1 | High | Runtime paths accept semantically invalid backend metadata values as success, so strict mode is bypassed on non-exception contract violations
   files: xyzgl/orchestrator/mirror.py, xyzgl/orchestrator/tutor_phases.py, xyzgl/router.py
   mission: Stop accepting semantically invalid backend metadata as runtime success. Make the invalid field and verdict visible in artifacts so operators can remediate configuration defects without reproducing the run interactively.
   acceptance: Strict mode fails for malformed backend metadata values. | The router and runtime surfaces agree on the invalid contract verdict.
   nexus: Validate backend metadata fields even when no exception was thrown. | Keep strict mode aligned with semantic validity, not only crash behavior.

4. BUG-103 | phase 1 and 6 | High | Backend validation and fallback tooling accept non-UTF-8-safe backend strings, so probes can PASS while artifact emission still crashes
   files: tools/backend_contract_probe.py, tools/backend_fault_injector.py, tools/harness_turn.py, witness/core.py, xyzgl/router.py
   mission: Make backend strings UTF-8-safe before probes and artifact emission diverge. Force the runtime, probes, and artifact writers onto one validation contract so enterprise certification cannot pass a backend that later crashes during export.
   acceptance: A backend string that would crash artifact emission cannot still produce a green probe. | Tests cover both probe tooling and runtime artifact creation.
   nexus: Normalize or reject backend strings before witness/artifact paths consume them. | Keep tools and runtime on the same backend-name validation path.

