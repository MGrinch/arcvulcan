# signal_fidelity_port

Copies curated Signal Fidelity plugin-bank files into the repo under `xyzgl/` or `tools/`.

## What it does

- lists files available inside the shipped plugin bank
- copies one selected file into an allowed repo destination
- can apply a JSON plan with multiple copy actions
- refuses absolute paths, repo escapes, and overwrite-by-default

## Source root

The tool reads from:

- `signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/`

If that folder is missing, the tool exits with an error.

## Usage

List available plugin-bank files:

```bash
python tools/signal_fidelity_port.py --list
```

Copy one file into `xyzgl/` or `tools/`:

```bash
python tools/signal_fidelity_port.py --copy relative/path/to/file.py --to tools
```

Apply a JSON plan file:

```bash
python tools/signal_fidelity_port.py --plan plan.json
```

Allow replacing an existing destination file:

```bash
python tools/signal_fidelity_port.py --copy relative/path/to/file.py --to xyzgl --overwrite
```

## Plan format

`--plan` expects JSON shaped like:

```json
{
  "actions": [
    {"src": "relative/path/from/plugin/root.py", "to": "tools"},
    {"src": "relative/path/from/plugin/root.py", "to": "xyzgl"}
  ]
}
```

## Destination rules

- destination must be relative
- destination must stay inside the repo root
- destination must start with `xyzgl` or `tools`
- existing files are not overwritten unless `--overwrite` is set

## Outputs

- `--list` prints repo-relative plugin-bank file paths
- `--copy` prints the written destination path
- `--plan` prints JSON describing the applied writes
