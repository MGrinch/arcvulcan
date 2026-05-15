# doctor

Repo health check. Intended to be a quick “is this repo sane?” test before deeper work.

## What it checks (current)

- required files exist (north star, stable spec, harnesses, schemas)
- warns if `__pycache__/` or `*.pyc` are present (they should be ignored/untracked)
- warns if repo contamination artifacts are present (`.coverage`, `tmp*.json`, pre-existing `runs/` outputs)
- key files stay within the ~200 line budget
- basic import sanity (`xyzgl.router`)

Note: `doctor` sets `PYTHONDONTWRITEBYTECODE=1` to avoid generating bytecode in
common workflows.

## Usage

```bash
python tools/doctor.py
```

## Exit codes

- `0` PASS
- `1` FAIL
