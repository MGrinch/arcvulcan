# Grounding Injection Audit

**Goal:** ensure local curriculum grounding is injected correctly into the tutor prompt.

## What it checks
- Forces `grounding_mode=local` for the run.
- Normalizes `grounding_dir` to a repo-relative shipped source before comparing direct grounding against prompt injection, so ambient env overrides cannot change attribution.
- Compares `build_grounding(...)` output against the text between prompt markers:
  `<<<DAEDALUS_GROUNDING>>>` ... `<<<END_DAEDALUS_GROUNDING>>>`.
- Verifies all `[src:id:ordinal]` labels are present.

## Usage
```bash
python tools/grounding_injection_audit.py --issue ISSUE-YYYYMMDD-NNN --text "uneven fit-up and tack weld spacing"
```

## Outputs
- `runs/<run_id>/grounding_audit_report.json` (includes requested vs effective grounding source and any normalization notes)
- `runs/<run_id>/grounding_audit_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL