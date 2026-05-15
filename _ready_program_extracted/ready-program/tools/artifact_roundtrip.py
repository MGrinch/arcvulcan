#!/usr/bin/env python3
from __future__ import annotations

"""Artifact round-trip checker.

Given a JSON file or a runs/<run_id>/ directory, this tool:
  - parses JSON files
  - re-serializes them in canonical form
  - (optional) compares canonical text to the existing file (--strict)
  - (optional) rewrites files in canonical form (--fix)

This is a cheap way to catch:
  - non-JSON-safe values (NaN/Infinity)
  - unstable serialization
  - corrupted / partially-written artifacts

Exit codes:
  0 PASS
  1 FAIL
"""

import argparse
import json
import os
import random
import secrets
import sys
import time
from pathlib import Path
from run_paths import allocate_run_dir, runs_root
from issue_id import validate_issue_id

# Keep zip-distributed repos clean (avoid creating __pycache__/)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

# Local helper (tools/ is on sys.path when running `python tools/<tool>.py`)
from json_canon import dumps_canonical, write_json

MAX_JSON_FILE_BYTES = 20_000_000


def _run_id(issue: str, seed: int) -> str:
    # Deterministic id to match deterministic=true in run metadata.
    return f"{issue}-{seed}"


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_json(path: Path) -> tuple[object | None, str | None]:
    try:
        if int(path.stat().st_size) > MAX_JSON_FILE_BYTES:
            return None, f"read_error: file too large (> {MAX_JSON_FILE_BYTES} bytes)"
    except OSError as e:
        return None, f"read_error: {e!r}"
    try:
        raw = path.read_bytes()
    except OSError as e:
        return None, f"read_error: {e!r}"
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(txt, object_pairs_hook=_no_duplicate_pairs), None
    except Exception as e:
        return None, f"json_parse_error: {e!r}"


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(tmp), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            fd = None
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _discover_json_targets(target: Path) -> list[Path]:
    if target.is_file():
        return [target]

    files: set[Path] = set()
    files.update(p for p in target.glob("*.json") if p.is_file())

    child_runs = target / "child_runs"
    if child_runs.is_dir():
        files.update(p for p in child_runs.rglob("*.json") if p.is_file())

    return sorted(files)


def main() -> int:
    p = argparse.ArgumentParser(prog="artifact_roundtrip")
    p.add_argument("path", help="file.json or runs/<run_id>/ dir")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--strict", action="store_true", help="Fail if canonical serialization differs")
    p.add_argument("--fix", action="store_true", help="Rewrite files to canonical JSON")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    target = Path(args.path)
    if not target.exists():
        print(f"FAIL: not found: {target}")
        return 1

    target_is_dir = target.is_dir()
    files = _discover_json_targets(target)

    if not files:
        print("FAIL: no json files found")
        return 1

    run_id = _run_id(args.issue, args.seed)
    run_dir = allocate_run_dir(run_id)

    rows: list[dict] = []
    any_fail = False
    any_change = False
    any_strict_mismatch = False
    direct_fix_root = target.resolve() if target_is_dir else None
    direct_fix_target = target.resolve() if not target_is_dir else None

    for fp in files:
        if fp.is_symlink():
            rows.append({"file": str(fp), "status": "FAIL", "error": "symlink paths are not supported", "changed": False})
            any_fail = True
            continue
        doc, err = _load_json(fp)
        if err:
            rows.append({"file": str(fp), "status": "FAIL", "error": err, "changed": False})
            any_fail = True
            continue

        can = dumps_canonical(doc)
        changed = False

        if args.strict:
            try:
                orig = fp.read_text(encoding="utf-8")
                if orig != can:
                    changed = True
            except Exception:
                changed = True

        if args.fix:
            try:
                fp_resolved = fp.resolve()
                if target_is_dir:
                    fp_resolved.relative_to(direct_fix_root)
                elif fp_resolved != direct_fix_target:
                    raise ValueError("direct file target changed during processing")
                _atomic_write_text(fp, can)
                changed = True
            except Exception as e:
                rows.append({"file": str(fp), "status": "FAIL", "error": f"write_error: {e!r}", "changed": False})
                any_fail = True
                continue

        strict_mismatch = bool(args.strict and changed and not args.fix)
        if strict_mismatch:
            any_strict_mismatch = True

        any_change = any_change or changed
        row = {"file": str(fp), "status": "FAIL" if strict_mismatch else "PASS", "changed": bool(changed)}
        if strict_mismatch:
            row["error"] = "strict_mismatch: canonical serialization differs"
        rows.append(row)

    report = {
        "schema_version": "artifact_roundtrip_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "path": str(target),
        "strict": bool(args.strict),
        "fixed": bool(args.fix),
        "files": rows,
    }
    write_json(run_dir / "artifact_roundtrip_report.json", report)

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["artifact_roundtrip_report.json", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL"},
    }
    write_json(run_dir / "run.json", run_meta)

    if any_fail:
        print(f"FAIL: wrote outputs to {run_dir}")
        return 1

    if any_strict_mismatch:
        print(f"FAIL: strict mismatch; wrote outputs to {run_dir}")
        return 1

    print(f"PASS: wrote outputs to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
