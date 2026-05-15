#!/usr/bin/env python3
"""Signal Fidelity port helper (Option A).

- Lists plugin-bank files
- Copies selected files into xyzgl/ or tools/
- Never overwrites unless --overwrite

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "signal_fidelity_src" / "XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED"
_ALLOWED_DEST_ROOTS = {"xyzgl", "tools"}


def _fail(msg: str, *, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _incomplete(msg: str) -> None:
    _fail(f"INCOMPLETE: {msg}", code=2)


def _require() -> None:
    if not PLUGIN_ROOT.exists():
        _incomplete(f"Missing plugin bank folder: {PLUGIN_ROOT}")


def list_files() -> list[str]:
    _require()
    out = []
    for p in PLUGIN_ROOT.rglob("*"):
        if p.is_file() and p.name not in {".gitkeep"}:
            out.append(str(p.relative_to(PLUGIN_ROOT)))
    return sorted(out)


def _resolve_repo_dest(to_dir: str) -> Path:
    raw = (to_dir or "").strip()
    if not raw:
        _incomplete("Missing destination directory")
    rel = Path(raw)
    if rel.is_absolute():
        _incomplete("Refusing absolute destination path.")
    if not rel.parts or rel.parts[0] not in _ALLOWED_DEST_ROOTS:
        allowed = ", ".join(sorted(_ALLOWED_DEST_ROOTS))
        _incomplete(f"Destination must be under one of: {allowed}")
    dst = (REPO_ROOT / rel).resolve()
    try:
        dst.relative_to(REPO_ROOT.resolve())
    except Exception:
        _incomplete("Refusing destination outside repo root.")
    return dst


def copy_one(rel: str, to_dir: str, overwrite: bool) -> str:
    _require()
    src = (PLUGIN_ROOT / rel).resolve()
    if not src.exists() or not src.is_file():
        _incomplete(f"No such plugin file: {rel}")
    if PLUGIN_ROOT.resolve() not in src.parents and src != PLUGIN_ROOT.resolve():
        _incomplete("Refusing path escape outside plugin root.")
    dst_dir = _resolve_repo_dest(to_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists() and not overwrite:
        _incomplete(f"Refusing to overwrite: {dst} (use --overwrite)")
    shutil.copy2(src, dst)
    return str(dst)


def _load_plan(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        _incomplete(f"Could not read plan file: {e}")
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        _incomplete(f"Malformed plan JSON: {e.msg} at line {e.lineno} column {e.colno}")
    if not isinstance(plan, dict):
        _incomplete("Plan JSON must be an object")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        _incomplete("Plan JSON must contain a non-empty actions list")
    normalized = []
    for idx, act in enumerate(actions):
        if not isinstance(act, dict):
            _incomplete(f"Plan action[{idx}] must be an object")
        src = act.get("src")
        to = act.get("to")
        if not isinstance(src, str) or not src.strip():
            _incomplete(f"Plan action[{idx}] src must be a non-empty string")
        if not isinstance(to, str) or not to.strip():
            _incomplete(f"Plan action[{idx}] to must be a non-empty string")
        normalized.append({"src": src.strip(), "to": to.strip()})
    return {"actions": normalized}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--copy")
    ap.add_argument("--to")
    ap.add_argument("--plan")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    if a.list:
        for f in list_files():
            print(f)
        return 0
    if a.plan:
        plan = _load_plan(Path(a.plan))
        results = []
        for act in plan.get("actions", []):
            results.append({"src": act["src"], "written": copy_one(act["src"], act["to"], a.overwrite)})
        print(json.dumps({"applied": results}, indent=2))
        return 0
    if a.copy:
        if not a.to:
            _incomplete("--copy requires --to")
        print(copy_one(a.copy, a.to, a.overwrite))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
