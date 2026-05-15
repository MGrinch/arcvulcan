# Latency/Cost Budget Enforcer

**Goal:** enforce simple performance budgets for the tutor/mirror paths.

## What it checks
- Tutor `p95` latency (from `tutor_meta.latency_ms`).
- Mirror `p95` latency if `DAEDALUS_ENABLE_MIRROR=1`.
- Estimated token budget (rough `ceil((prompt_chars+reply_chars)/4)`).

## Usage
```bash
python tools/latency_cost_budget_enforcer.py --issue ISSUE-YYYYMMDD-NNN --p95-ms 2500 --max-est-tokens 4096
```

## Outputs
- `runs/<run_id>/latency_budget_report.json`
- `runs/<run_id>/latency_budget_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS (budgets met)
- 1 FAIL (budget exceeded)
- 2 INCOMPLETE (reserved)

## Notes
Token counts are **estimates** (they vary by model/tokenizer). This is meant to flag
obvious regressions, not exact billing.