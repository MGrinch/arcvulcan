# Mutation Suite

**Goal:** detect weak assertions / missing invariants via mutation testing.

## Engines

### Builtin (default, no dependencies)
Runs a tiny deterministic mutation check against the current `xyzgl/router.py` reply and input-normalization anchors, and uses `tools/selfcheck.py` as the test oracle.

```bash
python tools/mutation_suite.py --issue ISSUE-YYYYMMDD-NNN
```

### cosmic-ray (optional)
A real mutation engine for deeper coverage.

```bash
pip install cosmic-ray
python tools/mutation_suite.py --issue ISSUE-YYYYMMDD-NNN --engine cosmic-ray --dry-run
python tools/mutation_suite.py --issue ISSUE-YYYYMMDD-NNN --engine cosmic-ray
```

## Outputs
- `runs/<run_id>/mutation_report.json`
- `runs/<run_id>/mutation_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL
- 2 INCOMPLETE (e.g., missing engine)
