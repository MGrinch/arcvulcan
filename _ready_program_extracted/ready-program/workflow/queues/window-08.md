# Window 08 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/targeted_sweep.py
  - tools/doctor.py
  - tools/reground_cadence_verifier.py

- Delivery standard:
  - Forward determinism and path flags all the way into child tools.
  - Do not sanitize away the exact run paths the parent needs.
  - Repo validation must happen before any contaminating writes.

1. BUG-45 | phase 5 | Medium | `targeted_sweep.py` sanitizes child output before extracting run paths
   files: tools/targeted_sweep.py
   mission: Preserve raw child output long enough to extract the run paths it contains. Keep the safe-output path compatible with production logging while still preserving the audit breadcrumbs that make sweep artifacts commercially supportable.
   acceptance: targeted_sweep still finds child run paths after sanitization changes. | Diagnostics remain safe without erasing the path signal.
   nexus: Separate path extraction from cosmetic output sanitization. | Only sanitize after the parent has captured the child bundle location.

2. BUG-67 | phase 5 | High | `targeted_sweep.py` contaminates the repo before running `doctor`
   files: tools/doctor.py, tools/targeted_sweep.py
   mission: Run repo health checks before targeted_sweep contaminates the working tree. This should make the tool safe for premium CI and customer demo environments where false repo dirtiness destroys confidence.
   acceptance: doctor sees the real pre-sweep repo state. | targeted_sweep no longer dirties the repo before validation.
   nexus: Move doctor or cleanliness checks ahead of any write-producing step. | Keep sweep setup from masking the repo state it was supposed to verify.

