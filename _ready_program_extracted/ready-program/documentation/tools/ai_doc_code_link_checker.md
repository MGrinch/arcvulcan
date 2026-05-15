# doc_code_link_checker

Checks **doc↔code governance links**.

## Checks

1. Every path listed in `docs/AI_INDEX.json` exists.
2. Every `tools/*.py` has companion docs:
   - `documentation/tools/ai_<tool>.md`
   - `documentation/tools/ai_<tool>.txt`

Missing tool docs are warnings by default. Use `--enforce` to fail.

## Usage

```bash
python tools/doc_code_link_checker.py --issue ISSUE-YYYYMMDD-NNN
```

Enforce missing tool docs:

```bash
python tools/doc_code_link_checker.py --issue ISSUE-YYYYMMDD-NNN --enforce
```

## Outputs

- `runs/<new_run_id>/doc_link_report.json`

Exit codes:
- `0` PASS
- `1` FAIL
