# Backend Contract Probe

**Goal:** verify Tutor/Mirror backends satisfy the internal `generate()` contract.

## What it checks
- `generate(prompt, seed=...)` returns an object with fields: `text`, `backend`, `model`, `latency_ms`.
- `latency_ms` is a non-negative integer.
- Basic smoke that the backend can produce a reply.

## Usage
```bash
python tools/backend_contract_probe.py --issue ISSUE-YYYYMMDD-NNN
```

To enable network backends (Gemini/Ollama), explicitly allow it:
```bash
python tools/backend_contract_probe.py --issue ISSUE-YYYYMMDD-NNN --allow-network
```

## Outputs
- `runs/<run_id>/backend_contract_report.json`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL (contract broken / exception)
- 2 INCOMPLETE (network backends requested but disabled)
