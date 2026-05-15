#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Avoid generating __pycache__/ in normal workflows (keeps repo clean in zip form)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MAX_LINES = 200
MAX_LINE_COUNT_BYTES = 5_000_000
MAX_REPO_ENTRIES_DEFAULT = 250_000

REQUIRED = [
    "NORTH_STAR.md",
    "00_NAVIGATOR_DRIVER_START_HERE.md",
    "STABLE/WORKFLOW_ASSISTANT.md",
    "STABLE/SPEC_v3.0.2.md",
    "STABLE/WITNESS_PROTOCOL_v2.1.md",
    "STABLE/docs/KNOWN_ISSUES.md",
    "tools/harness_turn.py",
    "tools/harness_lattice.py",
    "tools/validate_schemas.py",
    "schemas/witness_event.schema.json",
    "schemas/turn_report.schema.json",
    "schemas/lattice_report.schema.json",
    "schemas/run_meta.schema.json",
    "STABLE/ROLE_PROTOCOL.md",
    "documentation/grounding/ai_grounding.md",
    "documentation/protocols/ai_role_protocol.md",
    "curriculum/manifest.json",
]


def _line_count(p: Path) -> int:
    try:
        if p.stat().st_size > MAX_LINE_COUNT_BYTES:
            return MAX_LINES + 1
        with p.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _is_within_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(_REPO_ROOT.resolve())
        return True
    except Exception:
        return False


def _is_safe_repo_file(p: Path) -> bool:
    if p.is_symlink():
        return False
    if not p.is_file():
        return False
    return _is_within_repo(p)


def _max_repo_entries() -> int:
    raw = os.getenv("DAEDALUS_DOCTOR_MAX_ENTRIES", "").strip()
    if not raw:
        return MAX_REPO_ENTRIES_DEFAULT
    try:
        val = int(raw)
    except Exception:
        return MAX_REPO_ENTRIES_DEFAULT
    if val < 10_000:
        return 10_000
    return min(val, 2_000_000)


def _iter_repo_entries(root: Path, *, max_entries: int):
    root_resolved = root.resolve()
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(dirpath)

        kept_dirs: list[str] = []
        for d in dirnames:
            dp = base / d
            try:
                if dp.is_symlink():
                    continue
                dp.resolve().relative_to(root_resolved)
            except Exception:
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for d in kept_dirs:
            seen += 1
            if seen > max_entries:
                raise RuntimeError(f"repo walk exceeded entry cap ({max_entries})")
            yield base / d
        for fn in filenames:
            fp = base / fn
            try:
                if fp.is_symlink():
                    continue
                fp.resolve().relative_to(root_resolved)
            except Exception:
                continue
            seen += 1
            if seen > max_entries:
                raise RuntimeError(f"repo walk exceeded entry cap ({max_entries})")
            yield fp


def main() -> int:
    ap = argparse.ArgumentParser(prog="doctor")
    ap.add_argument(
        "--lenient",
        action="store_true",
        help="Exit 0 even when warnings exist (prints PASS + WARN). Default is strict (INCOMPLETE on warnings).",
    )
    args = ap.parse_args()

    problems: list[str] = []
    warnings: list[str] = []
    max_entries = _max_repo_entries()

    # required files
    for rel in REQUIRED:
        if not (_REPO_ROOT / rel).exists():
            problems.append(f"missing required file: {rel}")

    try:
        # caches (warn by default; in git these should be ignored/untracked)
        for p in _iter_repo_entries(_REPO_ROOT, max_entries=max_entries):
            if p.is_dir() and p.name == "__pycache__":
                warnings.append(f"cache dir present: {p.relative_to(_REPO_ROOT)}")
        for p in _iter_repo_entries(_REPO_ROOT, max_entries=max_entries):
            if p.is_file() and p.suffix.lower() == ".pyc":
                warnings.append(f"bytecode file present: {p.relative_to(_REPO_ROOT)}")

        # editor/backup artifacts (should not ship)
        for p in _iter_repo_entries(_REPO_ROOT, max_entries=max_entries):
            if not p.is_file():
                continue
            if p.name.endswith(".bak") or p.name.endswith("~"):
                warnings.append(f"backup artifact present: {p.relative_to(_REPO_ROOT)}")

        # repo contamination artifacts (should not ship in zips / commits)
        if (_REPO_ROOT / ".coverage").exists():
            warnings.append(".coverage present (remove before distributing)")
        for t in sorted(_REPO_ROOT.glob("tmp*.json")):
            warnings.append(f"temp json present: {t.name} (remove before distributing)")
        runs_dir = _REPO_ROOT / "runs"
        if runs_dir.exists():
            # ignore empty runs/ or runs/.gitkeep
            file_count = 0
            for p in _iter_repo_entries(runs_dir, max_entries=max_entries):
                if not p.is_file():
                    continue
                if p.name == ".gitkeep":
                    continue
                file_count += 1
            if file_count:
                warnings.append(f"runs/ contains {file_count} file(s) (clean before distributing)")

        # line budget (exclude runs/)
        for p in _iter_repo_entries(_REPO_ROOT, max_entries=max_entries):
            if not p.is_file():
                continue
            if "runs" in p.parts:
                continue
            if p.suffix.lower() not in {".py", ".md", ".txt"}:
                continue
            n = _line_count(p)
            if n > MAX_LINES:
                problems.append(f"line budget exceeded ({n}>{MAX_LINES}): {p.relative_to(_REPO_ROOT)}")
    except RuntimeError as e:
        print(f"INCOMPLETE: {e}")
        return 2

    # import sanity
    try:
        from xyzgl.router import route_turn  # noqa: F401
    except Exception as e:
        problems.append(f"import failed: xyzgl.router ({e!r})")

    if problems:
        print("FAIL:")
        for pr in problems:
            print(" -", pr)
        return 1

    # Strict by default: warnings mean the repo is not distribution-clean.
    if warnings and not args.lenient:
        print("INCOMPLETE: repo not distribution-clean")
        for w in warnings:
            print(" -", w)
        return 2

    print("PASS: repo looks ok")
    if warnings:
        print("WARN:")
        for w in warnings:
            print(" -", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
