#!/usr/bin/env python3
from __future__ import annotations

"""Latency + cost budget enforcer.

Runs a small scenario set and fails if latency/cost exceeds thresholds.

Notes:
  - Latency is read from tutor_meta.latency_ms (and mirror_meta.latency_ms if enabled).
  - "Token" cost is an estimate: ceil(chars/4).

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

import argparse
import json
import math
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


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    k = max(0, math.ceil(0.95 * len(s)) - 1)
    if k >= len(s):
        k = len(s) - 1
    return int(s[k])


def _tok_est(chars: int) -> int:
    c = max(0, int(chars))
    return (c + 3) // 4


def main() -> int:
    p = argparse.ArgumentParser(prog="latency_cost_budget_enforcer")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--turn-index", type=int, default=0)
    p.add_argument("--cases", type=int, default=5)
    p.add_argument("--p95-ms", type=int, default=2500)
    p.add_argument("--max-est-tokens", type=int, default=4096)
    p.add_argument("--text", default="Explain 2F vs 1F in welding")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    try:
        args.cases = int(args.cases)
    except Exception:
        print("INCOMPLETE: invalid --cases")
        return 2
    if args.cases < 1:
        print("INCOMPLETE: --cases must be >= 1")
        return 2
    try:
        args.p95_ms = int(args.p95_ms)
        args.max_est_tokens = int(args.max_est_tokens)
    except Exception:
        print("INCOMPLETE: invalid thresholds")
        return 2
    if args.p95_ms < 0 or args.max_est_tokens < 0:
        print("INCOMPLETE: thresholds must be >= 0")
        return 2

    from xyzgl.config import XYZGLConfig
    from xyzgl.prompting import build_tutor_prompt
    from xyzgl.router import route_turn

    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=False,
        mirror_send_user_content=False,
        llm_backend="stub",
    )

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    samples: list[dict] = []
    t_lat: list[int] = []
    m_lat: list[int] = []
    tok_estimates: list[int] = []

    for i in range(args.cases):
        seed_i = args.seed + i
        prompt, _meta = build_tutor_prompt(args.text, cfg=cfg, turn_index=args.turn_index)
        out = route_turn(args.text, seed=seed_i, cfg=cfg, turn_index=args.turn_index)
        reply = str(out.get("reply") or "")
        tutor_ms = int((out.get("tutor_meta") or {}).get("latency_ms") or 0)
        mirror_ms = int((out.get("mirror_meta") or {}).get("latency_ms") or 0) if cfg.enable_mirror else 0
        est_tokens = _tok_est(len(prompt) + len(reply))

        t_lat.append(tutor_ms)
        if cfg.enable_mirror:
            m_lat.append(mirror_ms)
        tok_estimates.append(est_tokens)

        samples.append(
            {
                "case": i,
                "seed": seed_i,
                "tutor_latency_ms": tutor_ms,
                "mirror_latency_ms": mirror_ms,
                "prompt_chars": len(prompt),
                "reply_chars": len(reply),
                "est_tokens": est_tokens,
                "backend": out.get("backend"),
            }
        )

    report = {
        "schema_version": "latency_budget_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "turn_index": args.turn_index,
        "cases": args.cases,
        "thresholds": {"p95_ms": args.p95_ms, "max_est_tokens": args.max_est_tokens},
        "observed": {
            "tutor_latency_ms": {"p95": _p95(t_lat), "max": max(t_lat) if t_lat else 0},
            "mirror_latency_ms": {"p95": _p95(m_lat), "max": max(m_lat) if m_lat else 0} if cfg.enable_mirror else None,
            "est_tokens": {"p95": _p95(tok_estimates), "max": max(tok_estimates) if tok_estimates else 0},
        },
        "samples": samples,
    }
    write_json((run_dir / "latency_budget_report.json"), report)

    ok = (_p95(t_lat) <= args.p95_ms) and (_p95(tok_estimates) <= args.max_est_tokens)
    if cfg.enable_mirror:
        ok = ok and (_p95(m_lat) <= args.p95_ms)

    summary = [
        "# Latency/Cost Budget Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- tutor p95 ms: `{_p95(t_lat)}` (threshold `{args.p95_ms}`)",
        f"- est tokens p95: `{_p95(tok_estimates)}` (threshold `{args.max_est_tokens}`)",
    ]
    if cfg.enable_mirror:
        summary.append(f"- mirror p95 ms: `{_p95(m_lat)}` (threshold `{args.p95_ms}`)")
    (run_dir / "latency_budget_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["latency_budget_report.json", "latency_budget_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
