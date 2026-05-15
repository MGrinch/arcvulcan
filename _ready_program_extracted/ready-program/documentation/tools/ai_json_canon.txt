# ai_json_canon

Canonical JSON writer used across Daedalus tools and artifacts to keep run bundles **byte-stable**.

This is a small utility module (not a standalone CLI) that provides helpers like `write_json(path, obj)`.

## What it guarantees
- Stable key ordering (`sort_keys=True`)
- Stable formatting (`indent=2`)
- UTF-8 output (`ensure_ascii=False`)
- Trailing newline

## Usage (module)

Example (from repo root):

```bash
python - <<'PY'
from pathlib import Path
from json_canon import write_json

write_json(Path('runs/example.json'), {'b': 2, 'a': 1})
print(Path('runs/example.json').read_text(encoding='utf-8'))
PY
```

## Why this exists

Some tools validate that artifacts are already in canonical form (e.g. strict round-trip checks). Using this module prevents noisy diffs and makes golden baselines portable.
