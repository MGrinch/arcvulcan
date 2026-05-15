# Active Queue: Window 12

- Name: Backend Probes and Fault Injection
- Area: Owns backend contract probes, backend fault injectors, and backend-side validation bugs.
- Archived source queue: `queues/window-12.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 5
- Remaining items: 4

1. BUG-30 | original #3 | phase 6 | Medium | `backend_fault_injector.py` has a false-positive hole and omits key fault scenarios
   files: tools/backend_fault_injector.py
2. BUG-57 | original #7 | phase 6 | Medium | `backend_contract_probe.py` accepts boolean `latency_ms` values as valid integers
   files: tools/backend_contract_probe.py
3. BUG-91 | original #8 | phase 6 | High | Backend validation tools ignore stdout/stderr side effects and can leak secret-bearing output while reporting green or handled results
   files: tools/backend_contract_probe.py, tools/backend_fault_injector.py
4. BUG-97 | original #9 | phase 6 | Medium | `backend_contract_probe.py` misclassifies offline and local backend configuration defects because the no-network gate runs after backend construction
   files: tools/backend_contract_probe.py
