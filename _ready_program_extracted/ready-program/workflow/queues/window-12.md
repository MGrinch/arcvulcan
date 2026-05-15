# Window 12 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - tools/secret_scanner.py
  - tools/protocol_drift_radar.py
  - tools/graph_invariant_checker.py
  - tools/mirror_leakage_detector.py

- Delivery standard:
  - Large or oddly formatted files must still be scanned intentionally.
  - Severity caps must not hide later HIGH findings.
  - Reports must not trust user-provided labels over embedded artifact truth.

1. BUG-64 | phase 6 | High | `tools/secret_scanner.py` silently skips large text files
   files: tools/secret_scanner.py
   mission: Scan large text files intentionally instead of silently skipping them. Large-corpus trust is part of the commercial value proposition, so the scanner must never fail open on the files customers care about most.
   acceptance: Large text files no longer disappear from secret scanning without a verdict. | Regression proves the scanner still handles large files predictably.
   nexus: Replace the silent size skip with bounded scanning or an explicit surfaced verdict. | Keep performance controls observable rather than invisible.

2. BUG-73 | phase 6 | Medium | `protocol_drift_radar.py` ignores `session_summary.md` in directory scans
   files: tools/protocol_drift_radar.py
   mission: Teach protocol_drift_radar to inspect session_summary.md when scanning directories. Expand the scan so the summary surface becomes a dependable review artifact rather than a blind spot in premium audit workflows.
   acceptance: Directory scans include session_summary.md findings. | The added coverage does not break existing scan semantics.
   nexus: Include session_summary.md in the directory scan artifact set. | Keep the added surface aligned with existing drift heuristics.

