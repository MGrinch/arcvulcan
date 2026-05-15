# Window 13 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/backend_contract_probe.py
  - tools/backend_fault_injector.py

- Delivery standard:
  - A PASS result must mean a real probe occurred.
  - Backend-side leaks and side effects must be part of the verdict.
  - Offline gating must happen before any backend object can misclassify the environment.

1. BUG-91 | phase 6 | High | Backend validation tools ignore stdout/stderr side effects and can leak secret-bearing output while reporting green or handled results
   files: tools/backend_contract_probe.py, tools/backend_fault_injector.py
   mission: Treat stdout/stderr side effects as first-class backend validation evidence. Side-effect truthfulness is what keeps backend certification credible in regulated or customer-hosted environments.
   acceptance: Secret-bearing or unsafe side effects affect the final probe verdict. | Backend validation reports include side-effect-aware reasoning.
   nexus: Capture and judge side effects instead of hiding them behind green or handled outcomes. | Prevent secret-bearing output from becoming an invisible side channel.

2. BUG-97 | phase 6 | Medium | `backend_contract_probe.py` misclassifies offline and local backend configuration defects because the no-network gate runs after backend construction
   files: tools/backend_contract_probe.py
   mission: Run the no-network gate before backend construction can misclassify the environment. Clean defect classification makes the probe more supportable and keeps offline SKUs from looking broken for the wrong reason.
   acceptance: Offline and local backend defects are classified correctly before backend construction. | The probe no longer mislabels network-gated environments.
   nexus: Move offline/local gating ahead of backend object creation. | Keep offline misconfiguration distinct from post-construction backend failures.

