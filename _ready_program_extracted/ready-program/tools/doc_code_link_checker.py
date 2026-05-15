#!/usr/bin/env python3
from __future__ import annotations

"""Doc↔code link checker.

Daedalus follows a 1:1 governance style: major code surfaces must have a
canonical doc companion.

This tool checks two things:
  1) `docs/AI_INDEX.json` references valid paths
  2) each `tools/<name>.py` has corresponding doc stubs:
     `documentation/tools/ai_<name>.md` and `.txt`

By default, missing tool docs are warnings. Use --enforce to fail.

Exit codes:
  0 PASS
  1 FAIL
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir
from issue_id import validate_issue_id

_REPO_ROOT = Path(__file__).resolve().parents[1]


_DOC_ALIAS = {
    # harness tools use ai_debug_harness_* docs
    "harness_turn": "debug_harness_turn",
    "harness_session": "debug_harness_session",
    "harness_lattice": "debug_harness_lattice",
}
MAX_AI_INDEX_SURFACES = 5000
MAX_AI_INDEX_BYTES = 5_000_000
INTERNAL_RUN_ID_SEED = 1337


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_json(p: Path) -> dict:
    if not p.exists() or not p.is_file():
        raise ValueError(f"invalid json path: {p}")
    try:
        if int(p.stat().st_size) > MAX_AI_INDEX_BYTES:
            raise ValueError(f"AI_INDEX too large: {p.stat().st_size} bytes > {MAX_AI_INDEX_BYTES}")
    except OSError:
        pass
    raw = p.read_bytes()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="replace")
    doc = json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
    return doc if isinstance(doc, dict) else {}


def _resolve_ai_index_path(repo_root: Path, raw_path: object) -> Path | None:
    s = str(raw_path or "").strip()
    if not s:
        return None
    p = Path(s)
    if p.is_absolute() or ".." in p.parts:
        return None
    try:
        resolved = (repo_root / p).resolve()
        resolved.relative_to(repo_root.resolve())
    except Exception:
        return None
    return resolved


def _tool_docs_missing(repo_root: Path) -> list[str]:
    missing: list[str] = []
    tool_dir = repo_root / "tools"
    doc_dir = repo_root / "documentation" / "tools"
    for py in sorted(tool_dir.glob("*.py")):
        name = py.stem
        # allow some meta scripts without docs
        if name in {"lattice_lib"}:
            continue
        doc_base = _DOC_ALIAS.get(name, name)
        md = doc_dir / f"ai_{doc_base}.md"
        txt = doc_dir / f"ai_{doc_base}.txt"
        if not md.exists() or not txt.exists():
            missing.append(name)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(prog="doc_code_link_checker")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--enforce", action="store_true", help="Fail on missing tool docs")
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    # Fixed internal entropy only for the ephemeral run-id suffix; this tool
    # must not serialize that implementation detail as caller-auditable seed
    # provenance because the CLI exposes no --seed contract.
    random.seed(INTERNAL_RUN_ID_SEED)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    ai_index_path = _REPO_ROOT / "docs" / "AI_INDEX.json"
    problems: list[str] = []
    warnings: list[str] = []

    if not ai_index_path.exists():
        warnings.append("docs/AI_INDEX.json missing")
    else:
        try:
            idx = _load_json(ai_index_path)
            surfaces = idx.get("surfaces") or []
            if not isinstance(surfaces, list):
                problems.append("AI_INDEX.surfaces must be a list")
            else:
                if len(surfaces) > MAX_AI_INDEX_SURFACES:
                    warnings.append(f"AI_INDEX surfaces truncated at {MAX_AI_INDEX_SURFACES} entries")
                for idx_surface, s in enumerate(surfaces[:MAX_AI_INDEX_SURFACES]):
                    if not isinstance(s, dict):
                        problems.append(f"AI_INDEX surface[{idx_surface}] must be an object")
                        continue
                    p = s.get("path")
                    if p is None:
                        problems.append(f"AI_INDEX surface[{idx_surface}] missing path")
                        continue
                    if not isinstance(p, str) or not p.strip():
                        problems.append(f"AI_INDEX surface[{idx_surface}] path must be a non-empty string")
                        continue
                    resolved = _resolve_ai_index_path(_REPO_ROOT, p)
                    if resolved is None:
                        problems.append(f"AI_INDEX path invalid: {p}")
                        continue
                    if not resolved.exists():
                        problems.append(f"AI_INDEX path missing: {p}")
        except Exception as e:
            problems.append(f"AI_INDEX load failed: {e}")

    missing_tools = _tool_docs_missing(_REPO_ROOT)
    if missing_tools:
        msg = "missing tool docs for: " + ", ".join(missing_tools)
        if args.enforce:
            problems.append(msg)
        else:
            warnings.append(msg)

    overall = "PASS" if not problems else "FAIL"
    report = {
        "schema_version": "doc_link_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "overall": overall,
        "problems": problems,
        "warnings": warnings,
        "missing_tools": missing_tools,
    }
    write_json((run_dir / "doc_link_report.json"), report)

    summary_lines = [
        "# Doc↔Code Link Checker Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- missing_tools: `{len(missing_tools)}`",
        f"- problems: `{len(problems)}`",
        f"- warnings: `{len(warnings)}`",
        "",
    ]
    if problems:
        summary_lines.append("## Problems")
        summary_lines += [f"- {p}" for p in problems[:50]]
        summary_lines.append("")
    if warnings:
        summary_lines.append("## Warnings")
        summary_lines += [f"- {w}" for w in warnings[:50]]
        summary_lines.append("")
    (run_dir / "doc_link_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "deterministic": True,
        "outputs": ["doc_link_report.json", "doc_link_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(f"{overall}: wrote outputs to {run_dir}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
