# Schemas

This repo uses JSON Schemas under `schemas/` to validate debug harness outputs.

## Files

- `schemas/witness_event.schema.json`
  - base envelope written by `witness.core.WitnessCore`
- `schemas/turn_report.schema.json`
  - validates `turn_report.json` (payload.turn_result)
- `schemas/lattice_report.schema.json`
  - validates `lattice_report.json` (payload.lattice_report)
- `schemas/run_meta.schema.json`
  - validates `run.json`
- `schemas/session_report.schema.json`
  - validates `session_report.json` (payload.session_report)
- `schemas/knowledge_graph.schema.json`
  - validates `knowledge_graph.json`

## Validate

```bash
python tools/validate_schemas.py runs/<run_id>/
```

`schemas/` is the canonical schema source for the repo.
