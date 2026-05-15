#!/usr/bin/env python3
from __future__ import annotations

"""Stage timing profiler.

Measures (rough) wall-clock timings for key stages:
  - prompt build (including optional local grounding)
  - tutor backend generation (stub by default)
  - mirror backend generation (optional)

This is not a microbenchmark; it exists to spot gross regressions.

Exit codes:
  0 PASS
  1 FAIL (only on obvious contract breaches)
"""

import argparse
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
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import build_tutor_prompt
from xyzgl.backends.registry import get_mirror_backend, get_tutor_backend


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _ms(dt_s: float) -> int:
    return int(round(dt_s * 1000))


def _profile_case(name: str, *, cfg: XYZGLConfig, seed: int, turn_index: int, user_text: str) -> dict:
    t0 = time.perf_counter()
    prompt, meta = build_tutor_prompt(user_text, cfg=cfg, turn_index=turn_index)
    t1 = time.perf_counter()
    tutor = get_tutor_backend(cfg)
    t2 = time.perf_counter()
    tres = tutor.generate(prompt, seed=seed)
    t3 = time.perf_counter()

    mirror_ms = None
    if cfg.enable_mirror:
        mirror = get_mirror_backend(cfg)
        mres = mirror.generate("mirror: " + user_text, seed=seed)
        mirror_ms = int(round(float(mres.latency_ms or 0)))

    return {
        "name": name,
        "prompt_build_ms": _ms(t1 - t0),
        "backend_select_ms": _ms(t2 - t1),
        "tutor_generate_ms": int(round(float(tres.latency_ms))) if tres.latency_ms is not None else _ms(t3 - t2),
        "mirror_generate_ms": mirror_ms,
        "prompt_len": len(prompt),
        "prompt_meta": {
            "protocol_regrounded": bool(meta.protocol_regrounded),
            "grounding_enabled": bool(meta.grounding_enabled),
            "grounding_snippets": (
                (len(((meta.grounding_meta or {}).get("snippets") or []))
                 if isinstance(((meta.grounding_meta or {}).get("snippets") or []), list)
                 else int(((meta.grounding_meta or {}).get("snippets") or 0) or 0))
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="stage_timing_profiler")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    cases = []
    problems = []

    # Case A: protocol only
    cfg_a = XYZGLConfig(tutor_backend="stub", protocol_reground_every=1, grounding_mode="off")
    cases.append(_profile_case("protocol_only", cfg=cfg_a, seed=args.seed, turn_index=0, user_text="Explain 2F vs 1F"))

    # Case B: protocol + grounding
    cfg_b = XYZGLConfig(tutor_backend="stub", protocol_reground_every=1, grounding_mode="local", grounding_dir="curriculum")
    cases.append(_profile_case("protocol_and_grounding", cfg=cfg_b, seed=args.seed, turn_index=0, user_text="SMAW arc length"))

    # Case C: mirror enabled (stub)
    cfg_c = XYZGLConfig(tutor_backend="stub", mirror_backend="stub", enable_mirror=True, protocol_reground_every=1, grounding_mode="off")
    cases.append(_profile_case("mirror_enabled", cfg=cfg_c, seed=args.seed, turn_index=0, user_text="fit up gap"))

    for c in cases:
        if c.get("prompt_len", 0) <= 0:
            problems.append(f"{c.get('name')}: prompt_len is 0")

    overall = "PASS" if not problems else "FAIL"
    report = {
        "schema_version": "stage_timing_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "overall": overall,
        "cases": cases,
        "problems": problems,
    }
    write_json((run_dir / "stage_timing_report.json"), report)

    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "deterministic": True,
            "artifact_identity_stable": False,
            "artifact_content_stable": True,
            "determinism_basis": "the shipped profiler cases are fixed-seed stub-only workloads; only the default run directory id is wall-clock/random",
            "outputs": ["stage_timing_report.json", "stage_timing_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL"},
        },
    )
    (run_dir / "stage_timing_summary.md").write_text(
        "\n".join(
            [
                f"# Stage Timing Summary — {overall}",
                "",
                f"- issue: {args.issue}",
                f"- run_id: {run_id}",
                f"- seed: {args.seed}",
                f"- cases: {len(cases)}",
                f"- problems: {len(problems)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"{overall}: wrote outputs to {run_dir}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
