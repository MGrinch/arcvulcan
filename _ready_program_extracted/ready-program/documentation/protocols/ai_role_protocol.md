# Role Protocol Re-grounding (Every N Turns)

The Orchestrator can periodically **re-inject** the role protocol to prevent drift.

Source of truth: `STABLE/ROLE_PROTOCOL.md`.

---

## Configure

### Environment
```bash
export DAEDALUS_PROTOCOL_PATH=STABLE/ROLE_PROTOCOL.md
export DAEDALUS_PROTOCOL_REGROUND_EVERY=5
```

Rules:
- Turn **0** always includes the protocol.
- If `N <= 0`, only turn 0 includes it.

### CLI flags
```bash
python -m xyzgl.cli --protocol-reground-every 5 "Explain 2F vs 1F"
```

Interactive mode (multi-turn):
```bash
python -m xyzgl.cli --interactive --protocol-reground-every 3
```

Type lines; use `exit` to stop.

---

## Audit
Turn outputs include:
- `turn_index`
- `prompt_meta.protocol_regrounded`
- `prompt_meta.protocol_path`

So you can confirm when protocol re-grounding occurred.
