#!/usr/bin/env python3
"""Network-free smoke test for the orchestrated session loop.

Outputs:
  runs/<run_id>/session_report.json
  runs/<run_id>/session_smoke_summary.md
  runs/<run_id>/run.json

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from witness.core import WitnessCore
from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.session_loop import run_session


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
    p = argparse.ArgumentParser(prog="repro_session_smoke")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--max-turns", type=int, default=4)
    p.add_argument("--run-id", help="Optional run id (default: timestamp-based)")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(int(args.seed))

    run_id = (args.run_id or "").strip() or _run_id()
    run_dir = allocate_run_dir(run_id)

    cfg = XYZGLConfig(tutor_backend="stub", mirror_backend="stub", enable_mirror=True, protocol_reground_every=2)
    graph = default_graph()

    def input_provider(prompt: str):
        if "gravity" in (prompt or "").lower():
            return "1F vs 2F: gravity matters.", {"typing_ms": 2000}
        return "arc length.", {"typing_ms": 2000}

    with _env_patch({"GWEN_DISABLED": "1"}):
        rep, _ = run_session(
            session_id="SMOKE",
            cfg=cfg,
            seed=int(args.seed),
            max_turns=int(args.max_turns),
            graph=graph,
            input_provider=input_provider,
        )

    ok = True
    details = ""
    if not rep.turns:
        ok, details = False, "no turns"
    else:
        want = {0: True, 1: False, 2: True, 3: False}
        for t in rep.turns:
            got = bool((t.teach.prompt_meta or {}).get("protocol_regrounded"))
            exp = want.get(t.turn_index, got)
            if got != exp:
                ok, details = False, f"turn {t.turn_index}: protocol_regrounded={got} expected={exp}"
                break

    wc = WitnessCore()
    event = wc.make_event(args.issue, {"session_report": rep.to_json()})
    wc.write_event_json(event, str(run_dir / "session_report.json"))

    (run_dir / "session_smoke_summary.md").write_text(
        "# Session Smoke Summary\n\n"
        f"- issue: `{args.issue}`\n"
        f"- seed: `{args.seed}`\n"
        f"- run_id: `{run_id}`\n"
        f"- turns: `{len(rep.turns)}`\n\n"
        + ("PASS\n" if ok else f"FAIL: {details}\n"),
        encoding="utf-8",
    )

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": int(args.seed),
        "deterministic": True,
        "outputs": ["session_report.json", "session_smoke_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
