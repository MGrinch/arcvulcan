# run_paths

Shared utilities for allocating `runs/<run_id>/` directories in a **portable** way.

## Purpose

Some environments are read-only (e.g., mounted zip, locked workspace). `run_paths` ensures tools can still emit a run bundle by falling back to a temp runs root when needed.

## API

- `runs_root() -> Path`
  - Prefers `DAEDALUS_RUNS_DIR` if set.
  - Else prefers `./runs` if writable.
  - Else falls back to `/tmp/daedalus_runs`.

- `allocate_run_dir(run_id: str) -> Path`
  - Creates `<runs_root>/<run_id>/` and returns the path.

## Notes

- Tools should **not** create empty run dirs. Validate inputs first, or write a minimal `run.json` + report on FAIL/INCOMPLETE.

