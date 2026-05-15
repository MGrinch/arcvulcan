# Ontario Claims Citation Guard

**Goal:** catch Ontario-/code-specific claims that appear without grounding or explicit citations.

## What it checks
- Scans tutor text for keywords like `CSA`, `W47.1`, `W59`, `CWB`, `O. Reg`, `WSIB`, etc.
- If such terms appear, verifies either:
  - grounding snippets were injected (via `prompt_meta.grounding.snippets`), and/or
  - text includes citation markers like `[src:...]`.

## Usage
Audit-only:
```bash
python tools/ontario_claims_citation_guard.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN
```

Enforce (fail on unsupported claims):
```bash
python tools/ontario_claims_citation_guard.py runs/<run_id> --issue ISSUE-YYYYMMDD-NNN --enforce
```

## Outputs
- `runs/<run_id>/ontario_claims_report.json`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL (only when `--enforce` is set)