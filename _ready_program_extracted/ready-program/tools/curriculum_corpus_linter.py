#!/usr/bin/env python3
from __future__ import annotations

"""Curriculum corpus linter.

Validates curriculum/manifest.json and referenced source files.
Designed to fail fast on:
  - missing / duplicate source ids
  - missing files
  - invalid UTF-8 reads
  - duplicate content fingerprints

Exit codes: 0 PASS, 1 FAIL.
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_within(root: Path, rel_path: str) -> Path | None:
    raw = (rel_path or "").strip()
    if not raw or raw == ".":
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return None
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except Exception:
        return None
    return resolved


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def main() -> int:
    p = argparse.ArgumentParser(prog="curriculum_corpus_linter")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--dir", default="curriculum", help="grounding directory (default: curriculum)")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    gdir = _resolve_within(_REPO_ROOT, args.dir)
    if gdir is None:
        gdir = (_REPO_ROOT / "curriculum").resolve()
        gdir_error = f"invalid --dir (must be repo-relative and not '.'): {args.dir}"
    else:
        gdir_error = None
    manifest = gdir / "manifest.json"

    problems: list[str] = []
    warnings: list[str] = []
    sources_out: list[dict] = []

    if gdir_error:
        problems.append(gdir_error)

    if not manifest.exists():
        problems.append(f"missing manifest: {manifest}")
        data = {}
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="strict"))
        except Exception as e:
            problems.append(f"manifest unreadable/invalid json: {e}")
            data = {}

    schema_version = str(data.get("schema_version") or "")
    if schema_version and schema_version != "curriculum_manifest_v1":
        warnings.append(f"unexpected schema_version: {schema_version}")

    raw_sources = data.get("sources") or []
    if not isinstance(raw_sources, list) or not raw_sources:
        problems.append("manifest.sources must be a non-empty list")
        raw_sources = []

    seen_ids: set[str] = set()
    seen_hashes: dict[str, str] = {}

    for s in raw_sources:
        sd = _as_dict(s)
        sid = str(sd.get("id") or "").strip()
        title = str(sd.get("title") or sid)
        rel_path = str(sd.get("path") or "").strip()
        lic = str(sd.get("license") or "")
        raw_tags = sd.get("tags") or []
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []

        entry = {"id": sid, "title": title, "path": rel_path, "license": lic, "tags": tags}

        if not sid:
            problems.append("source missing id")
            continue
        if sid in seen_ids:
            problems.append(f"duplicate source id: {sid}")
        seen_ids.add(sid)

        if not rel_path:
            problems.append(f"{sid}: missing path")
            continue

        fpath = _resolve_within(gdir, rel_path)
        if fpath is None:
            problems.append(f"{sid}: invalid path outside grounding dir: {rel_path}")
            continue
        if not fpath.exists():
            problems.append(f"{sid}: missing file: {rel_path}")
            continue
        if not fpath.is_file():
            problems.append(f"{sid}: path is not a file: {rel_path}")
            continue

        try:
            _ = fpath.read_text(encoding="utf-8", errors="strict")
        except Exception as e:
            problems.append(f"{sid}: file not valid UTF-8: {rel_path} ({e})")
            continue

        fp = _sha256(fpath)
        entry["sha256"] = fp
        entry["bytes"] = fpath.stat().st_size

        if fp in seen_hashes:
            problems.append(f"duplicate content: {sid} and {seen_hashes[fp]} have same sha256")
        else:
            seen_hashes[fp] = sid

        sources_out.append(entry)

    ok = not problems
    report = {
        "schema_version": "corpus_lint_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "grounding_dir": str(gdir),
        "manifest": str(manifest),
        "sources_total": len(raw_sources),
        "sources_checked": len(sources_out),
        "pass": ok,
        "problems": problems,
        "warnings": warnings,
        "sources": sources_out,
    }
    write_json((run_dir / "corpus_lint_report.json"), report)

    lines = [
        "# Curriculum Corpus Lint Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- sources_checked: `{len(sources_out)}`",
        "",
    ]
    if ok:
        lines.append("- ✅ PASS")
    else:
        lines.append("- ❌ FAIL")
        lines.extend([f"  - {x}" for x in problems])
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.extend([f"- {w}" for w in warnings])
    (run_dir / "corpus_lint_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["corpus_lint_report.json", "corpus_lint_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
