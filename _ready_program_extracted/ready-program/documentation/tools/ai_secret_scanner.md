# secret_scanner

Dependency-free repository secret scanner.

## What it flags

- Google API keys (`AIza...`)
- OpenAI-style keys (`sk-...`)
- private key blocks
- generic `token/api_key/secret = ...` hardcodes

## Usage

```bash
python tools/secret_scanner.py --issue ISSUE-YYYYMMDD-NNN
```

Fail the CI gate on any hit:

```bash
python tools/secret_scanner.py --issue ISSUE-YYYYMMDD-NNN --enforce
```

## Outputs

- `runs/<new_run_id>/secret_scan_report.json`

Exit codes:
- `0` PASS
- `1` FAIL (only when `--enforce` and hits exist)