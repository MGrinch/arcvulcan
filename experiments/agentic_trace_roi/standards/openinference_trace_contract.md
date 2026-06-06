# OpenInference-Compatible Trace Contract

Status: local contract for pass-1 fixtures.

This is a small ArcVulcan trace shape intended to map cleanly onto
OpenTelemetry/OpenInference-style spans. It is not a new private tracing
standard. It is a fixture/export contract for local experiments.

## Span families

Each trace fixture should produce these span families when present:

| Span family | Purpose | Parent |
| --- | --- | --- |
| `agent.run` | One end-to-end task attempt | none |
| `agent.message` | User, assistant, or reviewer message | `agent.run` |
| `agent.tool_call` | Structured tool call, connector use, or API call | `agent.run` |
| `agent.command` | Shell or terminal command | `agent.run` |
| `agent.verifier` | Test, check, screenshot, parser, or validation command | `agent.run` |
| `agent.artifact` | File/report/span output | `agent.run` |

## Required trace fixture fields

```json
{
  "trace_id": "string",
  "source": "agenttrove|local|manual",
  "task_family": "code_repair|terminal|repo_triage|math|computer_use|unknown",
  "messages": [],
  "tool_calls": [],
  "commands": [],
  "observations": [],
  "outcome": "success|failure|unknown",
  "reward": null,
  "tags": []
}
```

## Required span attributes

Every emitted span should include:

- `trace.source`
- `trace.task_family`
- `trace.outcome`
- `trace.tags`
- `span.family`

Command spans should include:

- `command.text`
- `command.kind`
- `command.exit_code`
- `command.hypothesis`
- `command.expected_observation`
- `command.observed`

Verifier spans should include:

- `verifier.name`
- `verifier.exit_code`
- `verifier.passed`

## First ROI assertions

The first local checks are deliberately behavioral:

- a trace reads or inspects before patching;
- commands carry a hypothesis and expected observation;
- patching is followed by a verifier;
- repeated failed command count stays low;
- final success is not claimed without verifier evidence.

These are assertions for trace quality and agent discipline, not model quality.

