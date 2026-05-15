#!/usr/bin/env python3
from __future__ import annotations

"""Retrieval evaluation bench.

Runs a small deterministic benchmark over the local curriculum grounding corpus.

Bench format (JSON):
  {
    "schema_version": "retrieval_bench@1",
    "cases": [
      {"query": "...", "expect_source_ids": ["demo_fitup"]}
    ]
  }

Outputs:
  runs/<run_id>/retrieval_eval_report.json
  runs/<run_id>/retrieval_eval_summary.md
  runs/<run_id>/run.json

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE
"""

import argparse
import html
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

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MAX_BENCH_BYTES = 5_000_000
MAX_BENCH_CASES = 5_000
MAX_STORED_CASE_RESULTS = 1_500
MAX_SUMMARY_CASES = 300
MAX_SUMMARY_QUERY_CHARS = 180
_DEFAULT_BENCH_REL = "curriculum/retrieval_bench.json"
_DEFAULT_GROUNDING_DIR_REL = "curriculum"


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_bench(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        if int(path.stat().st_size) > MAX_BENCH_BYTES:
            return None
    except OSError:
        return None
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="replace")
    try:
        out = json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
    except json.JSONDecodeError:
        return None
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def _safe_query_for_md(text: str) -> str:
    t = str(text or "").replace("\r", " ").replace("\n", " ")
    if len(t) > MAX_SUMMARY_QUERY_CHARS:
        t = t[:MAX_SUMMARY_QUERY_CHARS] + "...<truncated>"
    t = t.replace("`", "'")
    return html.escape(t, quote=False)


def _resolve_bench_path(path_text: str) -> Path:
    candidate = Path(str(path_text or "").strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (_REPO_ROOT / candidate).resolve()


def _resolve_grounding_dir(path_text: str) -> Path | None:
    raw = str(path_text or "").strip()
    if not raw:
        return None
    from xyzgl.prompting import _resolve_within as _runtime_resolve_within

    return _runtime_resolve_within(_REPO_ROOT, raw)


def _is_default_shipped_paths(bench_path: Path, grounding_dir: Path) -> bool:
    return (
        bench_path.resolve() == (_REPO_ROOT / _DEFAULT_BENCH_REL).resolve()
        and grounding_dir.resolve() == (_REPO_ROOT / _DEFAULT_GROUNDING_DIR_REL).resolve()
    )


def _unique_expected_source_ids(raw_cases: list[object]) -> set[str]:
    out: set[str] = set()
    for case in raw_cases:
        if not isinstance(case, dict):
            continue
        for sid in case.get("expect_source_ids") or []:
            sid_text = str(sid).strip()
            if sid_text:
                out.add(sid_text)
    return out


def _validate_shipped_benchmark_contract(
    bench_path: Path, grounding_dir: Path, raw_cases: list[object], corpus_source_ids: set[str]
) -> str | None:
    if not _is_default_shipped_paths(bench_path, grounding_dir):
        return None
    expected_source_ids = _unique_expected_source_ids(raw_cases)
    if len(expected_source_ids) < 2:
        return "shipped benchmark is vacuous: expected sources collapse to a single source id"
    if len(corpus_source_ids) < 2:
        return "shipped curriculum is vacuous: corpus exposes fewer than two source ids"
    missing = sorted(expected_source_ids.difference(corpus_source_ids))
    if missing:
        return "shipped benchmark references missing source ids: " + ", ".join(missing)
    return None


def main() -> int:
    p = argparse.ArgumentParser(prog="retrieval_eval_bench")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--k", type=int, default=5, help="top-k snippets")
    p.add_argument("--mode", choices=["any", "all"], default="any")
    p.add_argument("--bench", default=_DEFAULT_BENCH_REL)
    p.add_argument("--grounding-dir", default=_DEFAULT_GROUNDING_DIR_REL)
    args = p.parse_args()
    try:
        args.k = int(args.k)
    except Exception:
        print("INCOMPLETE: invalid --k")
        return 2
    if args.k <= 0:
        print("INCOMPLETE: --k must be >= 1")
        return 2

    random.seed(args.seed)
    bench_path = _resolve_bench_path(args.bench)
    grounding_dir = _resolve_grounding_dir(args.grounding_dir)
    if grounding_dir is None or not grounding_dir.exists() or not grounding_dir.is_dir():
        print(f"INCOMPLETE: invalid grounding dir: {args.grounding_dir}")
        return 2

    bench = _load_bench(bench_path)
    raw_cases = (bench or {}).get("cases") or []
    if not bench or not raw_cases:
        print(f"INCOMPLETE: bench not found or empty: {bench_path}")
        return 2
    if not isinstance(raw_cases, list):
        print("INCOMPLETE: bench.cases must be a list")
        return 2
    if len(raw_cases) > MAX_BENCH_CASES:
        print(f"INCOMPLETE: bench has too many cases ({len(raw_cases)} > {MAX_BENCH_CASES})")
        return 2

    from xyzgl.grounding.corpus import load_corpus
    from xyzgl.grounding.retrieval import retrieve_snippets

    corpus = load_corpus(grounding_dir)
    if not corpus.passages:
        print("INCOMPLETE: no passages in corpus (check curriculum/manifest.json)")
        return 2

    contract_problem = _validate_shipped_benchmark_contract(
        bench_path, grounding_dir, raw_cases, {str(s.id) for s in corpus.sources if str(s.id).strip()}
    )
    if contract_problem:
        print(f"INCOMPLETE: {contract_problem}")
        return 2

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    cases_out = []
    dropped_case_rows = 0
    passed = 0
    total = 0

    for c in raw_cases:
        q = str(c.get("query") or "").strip()
        exp = [str(x) for x in (c.get("expect_source_ids") or []) if str(x).strip()]
        if not q or not exp:
            continue
        total += 1
        snips = retrieve_snippets(corpus, q, max_snippets=args.k)
        got: list[str] = []
        got_set: set[str] = set()
        for s in snips:
            sid = str(s.source_id)
            if sid not in got_set:
                got_set.add(sid)
                got.append(sid)
        exp_set = set(exp)

        if args.mode == "all":
            ok = exp_set.issubset(got_set)
        else:
            ok = bool(exp_set.intersection(got_set))
        passed += 1 if ok else 0
        row = {"query": q, "expect": exp, "got": got, "pass": ok}
        if len(cases_out) < MAX_STORED_CASE_RESULTS:
            cases_out.append(row)
        else:
            dropped_case_rows += 1

    recall = (passed / total) if total else 0.0
    ok = total > 0 and passed == total

    report = {
        "schema_version": "retrieval_eval_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "bench_path": str(bench_path),
        "grounding_dir": str(grounding_dir),
        "k": args.k,
        "mode": args.mode,
        "tests_total": total,
        "tests_passed": passed,
        "recall_at_k": round(recall, 4),
        "cases_dropped": dropped_case_rows,
        "cases": cases_out,
    }
    write_json((run_dir / "retrieval_eval_report.json"), report)

    summary = [
        "# Retrieval Eval Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- bench: `{bench_path}`",
        f"- k: `{args.k}`",
        f"- mode: `{args.mode}`",
        f"- passed: `{passed}/{total}`",
        f"- recall@k: `{round(recall, 4)}`",
        "",
    ]
    for c in cases_out[:MAX_SUMMARY_CASES]:
        mark = "OK" if c["pass"] else "FAIL"
        summary.append(f"- {mark} `{_safe_query_for_md(c['query'])}` -> got {c['got']}")
    if len(cases_out) > MAX_SUMMARY_CASES:
        summary.append(f"- ... omitted {len(cases_out) - MAX_SUMMARY_CASES} additional case rows")
    if dropped_case_rows > 0:
        summary.append(f"- ... dropped {dropped_case_rows} result rows from JSON report for memory safety")
    (run_dir / "retrieval_eval_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["retrieval_eval_report.json", "retrieval_eval_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
