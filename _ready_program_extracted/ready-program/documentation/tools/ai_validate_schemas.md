# validate_schemas

Validates harness output JSON files against the repo JSON Schemas in `schemas/`.

This is a guardrail for the “1:1 code ↔ docs” rule: harness outputs should be
well-formed and stable.

## Usage

Validate a run directory (auto-detects known filenames):
```bash
python tools/validate_schemas.py runs/<run_id>/
```

Validate a single file (auto-guess schema by filename):
```bash
python tools/validate_schemas.py runs/<run_id>/turn_report.json
```

If the filename is non-standard, provide `--schema`:
```bash
python tools/validate_schemas.py path/to/file.json --schema turn_report.schema.json
```

## Exit codes

- `0` PASS: all validations succeeded
- `1` FAIL: one or more files failed validation or schema not found
