#!/usr/bin/env python3
"""Repro: backend selection + fallback behavior (network-free).

This smoke test is deterministic and enforces:
  1) Selecting a real Tutor backend without required env produces a backend_error
     but still returns a stub reply (unless DAEDALUS_REQUIRE_REAL_BACKENDS=1)
  2) When DAEDALUS_REQUIRE_REAL_BACKENDS=1, missing config raises

Outputs (standard run bundle):
  runs/<run_id>/repro_backends_smoke_report.json
  runs/<run_id>/backend_smoke_summary.md
  runs/<run_id>/run.json

Exit codes: 0 PASS, 1 FAIL.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# Keep zip-distributed repos clean (avoid creating __pycache__/ during smoke runs)
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


@contextmanager
def _env_patch(pairs: dict[str, str | None]):
    old = {k: os.environ.get(k) for k in pairs}
    try:
        for k, v in pairs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main() -> int:
    p = argparse.ArgumentParser(prog="repro_backends_smoke")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    from xyzgl.router import route_turn

    keys = [
        "DAEDALUS_TUTOR_BACKEND",
        "DAEDALUS_MIRROR_BACKEND",
        "DAEDALUS_ENABLE_MIRROR",
        "DAEDALUS_GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DAEDALUS_GEMINI_MODEL",
        "DAEDALUS_REQUIRE_REAL_BACKENDS",
    ]

    scenarios: list[dict] = []

    s1_obs: dict = {}
    s1_pass = False
    s1_details = ""
    try:
        with _env_patch(
            {
                **{k: None for k in keys},
                "DAEDALUS_TUTOR_BACKEND": "gemini",
                "DAEDALUS_GEMINI_MODEL": "gemini-test-model",
            }
        ):
            out = route_turn("hello", seed=args.seed)
            s1_obs = {
                "requested_backend": out.get("backend"),
                "reply_len": len(out.get("reply") or ""),
                "has_backend_error": bool(out.get("backend_error")),
                "backend_error": out.get("backend_error"),
            }
            s1_pass = bool(out.get("reply")) and bool(out.get("backend_error"))
            if not s1_pass:
                s1_details = "expected non-empty reply and backend_error when Gemini key is missing"
    except Exception as e:
        s1_pass = False
        s1_details = f"unexpected exception: {type(e).__name__}: {e}"

    scenarios.append(
        {
            "name": "misconfigured_real_backend_falls_back",
            "pass": s1_pass,
            "observed": s1_obs,
            "details": s1_details,
        }
    )

    s2_pass = False
    s2_details = ""
    try:
        with _env_patch(
            {
                **{k: None for k in keys},
                "DAEDALUS_TUTOR_BACKEND": "gemini",
                "DAEDALUS_GEMINI_MODEL": "gemini-test-model",
                "DAEDALUS_REQUIRE_REAL_BACKENDS": "1",
            }
        ):
            _ = route_turn("hello", seed=args.seed)
            s2_pass = False
            s2_details = "expected route_turn to raise when DAEDALUS_REQUIRE_REAL_BACKENDS=1"
    except Exception as e:
        s2_pass = True
        s2_details = f"raised as expected: {type(e).__name__}"

    scenarios.append(
        {
            "name": "require_real_backends_raises",
            "expect_raise": True,
            "pass": s2_pass,
            "observed": {"raised": s2_pass},
            "details": s2_details,
        }
    )

    passed = sum(1 for s in scenarios if s.get("pass"))
    overall_ok = passed == len(scenarios)

    report = {
        "schema_version": "repro_backends_smoke_report@1",
        "tool": "repro_backends_smoke",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "scenarios_total": len(scenarios),
        "scenarios_passed": passed,
        "scenarios": scenarios,
    }
    write_json((run_dir / "repro_backends_smoke_report.json"), report)

    summary = [
        "# Backend Selection Smoke",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- seed: `{args.seed}`",
        "",
        f"- overall: **{'PASS' if overall_ok else 'FAIL'}**",
        "",
        "## Scenarios",
    ]
    for s in scenarios:
        status = "✅" if s.get("pass") else "❌"
        summary.append(f"- {status} `{s.get('name')}`")
        if s.get("details"):
            summary.append(f"  - {s.get('details')}")
    (run_dir / "backend_smoke_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["repro_backends_smoke_report.json", "backend_smoke_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if overall_ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
