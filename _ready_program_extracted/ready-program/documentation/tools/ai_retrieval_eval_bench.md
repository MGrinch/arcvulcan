# Retrieval Eval Bench

**Goal:** catch grounding retrieval regressions (query → source selection).

This tool runs a small deterministic benchmark over the local curriculum
corpus loaded from `curriculum/manifest.json`.

## Usage
```bash
python tools/retrieval_eval_bench.py --issue ISSUE-YYYYMMDD-NNN \
  --bench curriculum/retrieval_bench.json \
  --k 5 --mode any
```

## Outputs
- `runs/<run_id>/retrieval_eval_report.json`
- `runs/<run_id>/retrieval_eval_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS (all cases passed)
- 1 FAIL (one or more cases failed)
- 2 INCOMPLETE (bench or corpus missing)

## Notes
Keep the bench small and stable. Add new cases when you add new curriculum
sources or change retrieval logic.