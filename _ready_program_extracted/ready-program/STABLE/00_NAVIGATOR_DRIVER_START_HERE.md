# 00_NAVIGATOR_DRIVER_START_HERE.md (STABLE)

> Name: ArcVulcan (formerly Project Daedalus / XYZGL; see README for full name history).
Project name: ArcVulcan

Canonical navigator lives at repo root:
- `00_NAVIGATOR_DRIVER_START_HERE.md`

This STABLE stub exists so internal references can safely point to a stable path.

## Optional developer dependencies (high signal tools)

- Signal Fidelity Overlay:
  - `.rar` path needs an extractor (`7z` recommended), OR use `--overlay some.zip` / `--overlay some_dir/`.
- Coverage-guided fuzzing:
  - `pip install atheris` enables coverage fuzzing (fallback fuzzer works without it).
- Deep mutation testing:
  - `pip install cosmic-ray` (builtin mutation check works without it)
