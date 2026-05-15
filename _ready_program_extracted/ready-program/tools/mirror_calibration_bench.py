#!/usr/bin/env python3
from __future__ import annotations

"""Mirror calibration bench.

Computes simple similarity metrics between the Mirror prediction and the
actual learner answer in a session report.

Why:
  The Mirror is used as a self-supervision signal. When mirror quality
  degrades silently, the downstream correction/delta pipeline becomes noise.

This tool is network-free and works even with stub mirror.

Metrics:
  - Jaccard token overlap
  - difflib SequenceMatcher ratio

Exit codes:
  0 PASS
  1 FAIL (avg below --min-avg)
  2 INCOMPLETE (no mirror answers present)
"""

import argparse
import json
import math
import os
import random
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]

MAX_REPORT_BYTES = 5_000_000
MAX_SEQMATCH_CHARS = 512
MAX_TOKEN_COUNT = 4096
MAX_SCORED_TURNS = 5000
DEFAULT_MIN_AVG = 0.35


def _run_id() -> str:
    return make_run_id()


_TOK_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(s: str) -> set[str]:
    out: set[str] = set()
    for m in _TOK_RE.finditer((s or "").lower()):
        out.add(m.group(0))
        if len(out) >= MAX_TOKEN_COUNT:
            break
    return out


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta) + len(tb) - inter
    return (inter / float(union)) if union > 0 else 0.0


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_seqmatch(a: str, b: str) -> float:
    aa = (a or "").lower()
    bb = (b or "").lower()
    if not aa and not bb:
        return 1.0
    if not aa or not bb:
        return 0.0
    aa = aa[:MAX_SEQMATCH_CHARS]
    bb = bb[:MAX_SEQMATCH_CHARS]
    return SequenceMatcher(a=aa, b=bb).ratio()


def _is_within(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="mirror_calibration_bench")
    p.add_argument("path", help="session_report.json or runs/<run_id>/ dir")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--min-avg", type=float, default=DEFAULT_MIN_AVG, help="Fail if avg_seqmatch < min")
    p.add_argument(
        "--allow-external-path",
        action="store_true",
        help="Allow reading session reports outside repository root.",
    )
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2
    if not math.isfinite(args.min_avg):
        print("INCOMPLETE: --min-avg must be a finite float")
        return 2
    if args.min_avg < 0.0 or args.min_avg > 1.0:
        print("INCOMPLETE: --min-avg must be within [0.0, 1.0]")
        return 2

    random.seed(args.seed)
    target = Path(args.path).resolve()
    if target.is_dir():
        fp = (target / "session_report.json").resolve()
    else:
        fp = target
    if not fp.exists():
        print(f"FAIL: not found: {fp}")
        return 1
    if not args.allow_external_path and not _is_within(_REPO_ROOT, fp):
        print("INCOMPLETE: path must be within repo root unless --allow-external-path is set")
        return 2
    try:
        if int(fp.stat().st_size) > MAX_REPORT_BYTES:
            print(f"FAIL: report too large: {fp} ({fp.stat().st_size} bytes)")
            return 1
    except OSError:
        print(f"FAIL: unable to stat input: {fp}")
        return 1

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)

    try:
        doc = json.loads(fp.read_text(encoding="utf-8", errors="replace"), object_pairs_hook=_no_duplicate_pairs)
    except Exception as e:
        print(f"INCOMPLETE: invalid JSON input: {e}")
        return 2
    # Reports are wrapped as WitnessEvents.
    if isinstance(doc, dict) and doc.get("schema_version") == "witness_event@1":
        doc = ((doc.get("payload") or {}).get("session_report") or doc)
    turns = (doc.get("turns") or []) if isinstance(doc, dict) else []

    scores: list[dict] = []
    for t in turns:
        if len(scores) >= MAX_SCORED_TURNS:
            break
        td = _as_dict(t)
        tid = _as_int(td.get("turn_index"), 0)
        node_id = str(td.get("node_id") or "")
        mirror = _as_dict(td.get("mirror")).get("answer")
        user = _as_dict(td.get("eval")).get("user_answer")
        if not mirror:
            continue
        if user is None:
            continue
        j = _jaccard(mirror, user)
        s = _safe_seqmatch(str(mirror or ""), str(user or ""))
        scores.append({"turn_index": tid, "node_id": node_id, "jaccard": j, "seqmatch": s})

    n = len(scores)
    if n == 0:
        report = {
            "schema_version": "mirror_calibration_report@1",
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "path": str(fp),
            "n_scored": 0,
            "avg_jaccard": 0.0,
            "avg_seqmatch": 0.0,
            "min_avg": float(args.min_avg),
            "scores": [],
        }
        write_json((run_dir / "mirror_calibration_report.json"), report)
        write_json(
            (run_dir / "run.json"),
            {
                "run_id": run_id,
                "issue_id": args.issue,
                "seed": args.seed,
                "deterministic": True,
                "outputs": [
                "mirror_calibration_report.json",
                "mirror_calibration_summary.md",
                "run.json",
            ],
                "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
            },
        )
        (run_dir / "mirror_calibration_summary.md").write_text(
            "\n".join([
                "# Mirror Calibration — INCOMPLETE", "",
                f"- issue: {args.issue}", f"- run_id: {run_id}", f"- path: {fp}",
                "- n_scored: 0",
                f"- min_avg(seqmatch): {float(args.min_avg):.3f}",
            ]) + "\n",
            encoding="utf-8",
        )
        print(f"INCOMPLETE: no mirror answers present (wrote {run_dir})")
        return 2

    avg_j = sum(s["jaccard"] for s in scores) / n
    avg_s = sum(s["seqmatch"] for s in scores) / n

    report = {
        "schema_version": "mirror_calibration_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "path": str(fp),
        "n_scored": n,
        "avg_jaccard": avg_j,
        "avg_seqmatch": avg_s,
        "min_avg": float(args.min_avg),
        "scores": scores,
    }
    write_json((run_dir / "mirror_calibration_report.json"), report)
    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "deterministic": True,
            "outputs": [
                "mirror_calibration_report.json",
                "mirror_calibration_summary.md",
                "run.json",
            ],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    overall = "FAIL" if avg_s < float(args.min_avg) else "PASS"
    (run_dir / "mirror_calibration_summary.md").write_text(
        "\n".join([
            f"# Mirror Calibration — {overall}", "",
            f"- issue: {args.issue}", f"- run_id: {run_id}", f"- path: {fp}",
            f"- n_scored: {n}",
            f"- avg_jaccard: {avg_j:.3f}",
            f"- avg_seqmatch: {avg_s:.3f}",
            f"- min_avg(seqmatch): {float(args.min_avg):.3f}",
        ]) + "\n",
        encoding="utf-8",
    )
    if avg_s < float(args.min_avg):
        print(f"FAIL: avg_seqmatch {avg_s:.3f} < {args.min_avg:.3f} (wrote {run_dir})")
        return 1
    print(f"PASS: avg_seqmatch {avg_s:.3f} (wrote {run_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
