# Tool: repro_grounding_protocol_smoke

File: `tools/repro_grounding_protocol_smoke.py`

Purpose:
- Network-free verification that:
  - protocol re-grounding triggers on turn 0 and every N turns
  - local curriculum grounding returns at least one snippet when enabled

Usage:
```bash
python tools/repro_grounding_protocol_smoke.py --issue ISSUE-YYYYMMDD-NNN
```

Outputs:
- Prints PASS/FAIL only (no files).
- Intended to be called by `tools/selfcheck.py`.

Configuration:
- Uses `stub` backend + `grounding_mode=local` + corpus under `curriculum/`.
- Sets `protocol_reground_every=2` for quick coverage.
