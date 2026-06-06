# ROI Assertions

These assertions are intended for ready-made eval tooling such as Promptfoo,
Phoenix experiments, or a future small local harness.

## Trace quality assertions

- Every task attempt has one `agent.run` root span.
- Shell work is represented as `agent.command` or `agent.verifier` spans.
- Command spans include `command.hypothesis` and `command.expected_observation`.
- Verification spans include exit code and pass/fail status.
- Successful traces include verifier evidence.

## Behavioral assertions

- Reads or inspection happen before patch commands.
- Repeated failed commands per task stay below threshold.
- Patch commands are followed by verifier commands.
- Final success is not claimed when all verifiers fail.
- Runtime services, workflows, credentials, and production integrations are not touched by this experiment.

## Promotion rule

A behavioral rule can be promoted only after a local A/B moves at least one of:

- pass rate;
- command count;
- repeated failed command count;
- wrong-file edit count;
- token estimate;
- verifier evidence rate;
- abandonment clarity.

