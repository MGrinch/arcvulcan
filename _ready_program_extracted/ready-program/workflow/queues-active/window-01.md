# Active Queue: Window 01

- Name: Runtime Router and Sanitization
- Area: Owns router, protocol, mirror input-output, fallback, and sanitization runtime bugs.
- Archived source queue: `queues/window-01.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 7
- Remaining items: 6

1. BUG-01 | original #3 | phase 1 | High | Non-strict tutor backend fallback is unreachable
   files: xyzgl/orchestrator/tutor_phases.py, xyzgl/router.py
2. BUG-06 | original #6 | phase 1 | High | Raw mirror mode permits delimiter injection
   files: xyzgl/backends/stub.py, xyzgl/router.py
3. BUG-27 | original #7 | phase 1 | High | Invalid protocol paths silently downgrade to the fallback protocol
   files: xyzgl/prompting.py, xyzgl/protocols.py
4. BUG-54 | original #9 | phase 1 | High | Empty tutor output is silently accepted in `run_probe_phase()` and `run_eval_phase()`
   files: xyzgl/orchestrator/parsing.py, xyzgl/orchestrator/tutor_phases.py
5. BUG-83 | original #11 | phase 1 | High | Runtime paths accept semantically invalid backend metadata values as success, so strict mode is bypassed on non-exception contract violations
   files: xyzgl/orchestrator/mirror.py, xyzgl/orchestrator/tutor_phases.py, xyzgl/router.py
6. BUG-103 | original #13 | phase 1 and 6 | High | Backend validation and fallback tooling accept non-UTF-8-safe backend strings, so probes can PASS while artifact emission still crashes
   files: tools/backend_contract_probe.py, tools/backend_fault_injector.py, tools/harness_turn.py, witness/core.py, xyzgl/router.py
