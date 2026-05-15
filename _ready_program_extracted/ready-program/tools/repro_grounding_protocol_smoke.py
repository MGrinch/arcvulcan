#!/usr/bin/env python3
from __future__ import annotations

"""Network-free smoke test: protocol re-grounding + local grounding.

This is intentionally small and deterministic:
  - stub tutor (no networks)
  - local grounding from ./curriculum
  - protocol re-ground cadence every N turns

Outputs (standard run bundle):
  runs/<run_id>/repro_grounding_protocol_smoke_report.json
  runs/<run_id>/grounding_protocol_smoke_summary.md
  runs/<run_id>/run.json

Exit codes: 0 PASS, 1 FAIL.
"""

import argparse
import os
import random
import sys
import time
from pathlib import Path

# Keep zip-distributed repos clean
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.router import route_turn


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def main() -> int:
    p = argparse.ArgumentParser(prog="repro_grounding_protocol_smoke")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--every", type=int, default=2, help="Protocol reground cadence N")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=False,
        tutor_model="",
        mirror_model="",
        ollama_host="http://localhost:11434",
        protocol_path="STABLE/ROLE_PROTOCOL.md",
        protocol_reground_every=int(args.every),
        grounding_mode="local",
        grounding_dir="curriculum",
        grounding_max_snippets=3,
        grounding_max_chars=1200,
        enforce_determinism=True,
        max_chars_in=10_000,
        max_chars_out=10_000,
        llm_backend="stub",
    )

    steps: list[dict] = []

    # Turn 0 should reground protocol AND include grounding snippets
    t0 = route_turn("uneven tack gap", seed=args.seed, cfg=cfg, turn_index=0)
    ok0a = bool(t0.get("prompt_meta", {}).get("protocol_regrounded"))
    ok0b = bool(t0.get("prompt_meta", {}).get("grounding", {}).get("snippets"))
    exit0 = 0 if (ok0a and ok0b) else 1
    msg0 = f"turn0 protocol_regrounded={ok0a}, snippets={ok0b}"
    steps.append({"name": "turn0_reground_and_grounding", "exit_code": exit0, "stdout_tail": msg0})

    # Turn 1 should NOT reground (cadence N)
    t1 = route_turn("uneven tack gap", seed=args.seed, cfg=cfg, turn_index=1)
    ok1 = not bool(t1.get("prompt_meta", {}).get("protocol_regrounded"))
    exit1 = 0 if ok1 else 1
    msg1 = f"turn1 protocol_regrounded={bool(t1.get('prompt_meta', {}).get('protocol_regrounded'))}"
    steps.append({"name": "turn1_no_reground", "exit_code": exit1, "stdout_tail": msg1})

    # Turn N should reground
    tn = route_turn("uneven tack gap", seed=args.seed, cfg=cfg, turn_index=int(args.every))
    okn = bool(tn.get("prompt_meta", {}).get("protocol_regrounded"))
    exitn = 0 if okn else 1
    msgn = f"turn{int(args.every)} protocol_regrounded={okn}"
    steps.append({"name": "turnN_reground", "exit_code": exitn, "stdout_tail": msgn})

    overall = "PASS" if all(s["exit_code"] == 0 for s in steps) else "FAIL"

    report = {
        "schema_version": "repro_grounding_protocol_smoke_report@1",
        "tool": "repro_grounding_protocol_smoke",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "overall": overall,
        "steps": steps,
        "meta": {
            "every": int(args.every),
            "grounding_mode": cfg.grounding_mode,
            "grounding_dir": cfg.grounding_dir,
            "protocol_path": cfg.protocol_path,
        },
    }
    write_json((run_dir / "repro_grounding_protocol_smoke_report.json"), report)

    summary = [
        "# Grounding + Protocol Smoke",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- seed: `{args.seed}`",
        f"- every: `{int(args.every)}`",
        "",
        f"- overall: **{overall}**",
        "",
        "## Steps",
    ]
    for s in steps:
        status = "✅" if s["exit_code"] == 0 else "❌"
        summary.append(f"- {status} `{s['name']}` — {s.get('stdout_tail','')}")
    (run_dir / "grounding_protocol_smoke_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["repro_grounding_protocol_smoke_report.json", "grounding_protocol_smoke_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(f"{overall}: wrote outputs to {run_dir}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
