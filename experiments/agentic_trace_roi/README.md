# Agentic Trace ROI Scaffold

Status: pass-1 standards-first scaffold.

This experiment turns the AgentTrove leverage idea from PR #2 into a small,
local, measurable surface. It does not change ArcVulcan runtime behavior.

The governing direction is:

```text
AgentTrove/local traces -> standard span contract -> ready-made trace/eval tools -> custom diagnostic deltas only if needed
```

## Guardrails

- Do not fine-tune from this scaffold.
- Do not download full AgentTrove by default.
- Do not mutate production runtime behavior.
- Do not add heavyweight dependencies in pass 1.
- Do not claim improvement without an A/B measurement.

## Layout

```text
experiments/agentic_trace_roi/
  README.md
  adapters/
    agenttrove_to_trace_fixture.py
    trace_fixture_to_spans.py
  evals/
    promptfoo.example.yaml
    roi_assertions.md
  fixtures/
    tiny_failure_trace.jsonl
    tiny_success_trace.jsonl
  reports/
    .gitkeep
  standards/
    openinference_trace_contract.md
    trace_fixture.schema.json
```

## Deterministic local command

Run from the repository root:

```powershell
python experiments\agentic_trace_roi\adapters\trace_fixture_to_spans.py `
  --input experiments\agentic_trace_roi\fixtures\tiny_success_trace.jsonl `
  --input experiments\agentic_trace_roi\fixtures\tiny_failure_trace.jsonl `
  --output-spans experiments\agentic_trace_roi\reports\trace_spans.jsonl `
  --output-report experiments\agentic_trace_roi\reports\TRACE_ROI_V2_REPORT.md
```

Expected result:

- `reports/trace_spans.jsonl`
- `reports/TRACE_ROI_V2_REPORT.md`

The report is evidence of fixture ingestion and trace-shape readiness. It is
not evidence that any agent improved yet.

## Optional bounded AgentTrove local adapter

The adapter reads a local JSONL sample. It does not fetch Hugging Face data.

```powershell
python experiments\agentic_trace_roi\adapters\agenttrove_to_trace_fixture.py `
  --input path\to\small_agenttrove_sample.jsonl `
  --output experiments\agentic_trace_roi\reports\agenttrove_fixture_sample.jsonl `
  --sample-size 20
```

Samples over 20 require `--allow-large-sample` so large dataset use is always
intentional.

## Ready-made tool path

After pass 1, try ready-made infrastructure before custom mining:

1. Phoenix or another OpenTelemetry/OpenInference-compatible local trace viewer.
2. Promptfoo-style trace assertions for coding-agent behavior.
3. A tiny custom miner only if standardized trace export leaves a real signal gap.

