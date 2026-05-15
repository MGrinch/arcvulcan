# ai_debug_harness_lattice

**IMPLEMENTATION (2026-01-29): tool is runnable**

Runs a deterministic lattice (grid) of single-turn scenarios across parameter
settings (**seed, process, thickness, defect**) and produces a stability matrix.

This harness is meant to answer:
- “Did something break determinism?”
- “Do replies still satisfy baseline safety/format checks across a grid?”

## Usage

```bash
python tools/harness_lattice.py --issue ISSUE-20260129-001

# optional overrides (comma lists)
python tools/harness_lattice.py --issue ISSUE-20260129-001 \
  --seeds 1,1337,2026 \
  --processes SMAW,GMAW,FCAW \
  --thicknesses 3mm,6mm,12mm \
  --defects "uneven fit-up,porosity,undercut"
```

## Outputs

- `runs/<run_id>/lattice_report.json` (WitnessEvent containing payload.lattice_report)
- `runs/<run_id>/lattice_summary.md`
- `runs/<run_id>/run.json`

## Exit codes

- `0` PASS (all cases ok)
- `1` FAIL (one+ case check failed)
- `2` INCOMPLETE (unhandled exception)

## Checks (current)

Per case:
- reply is non-empty
- reply starts with `Safety first:`
- reply obeys `max_chars_out`
- deterministic: same `seed+text` => same reply
- basic metadata present: backend, input echo

## Risk scoring

Each case gets a **risk score (0–100)** derived from how many checks failed:
- 0 means all checks passed
- higher means more failed checks

Risk bands in the summary:
- GREEN (0)
- YELLOW (1–20)
- ORANGE (21–50)
- RED (51–100)

The summary also includes:
- Failure buckets (which checks fail most often)
- Worst cases table (highest-risk scenarios)
