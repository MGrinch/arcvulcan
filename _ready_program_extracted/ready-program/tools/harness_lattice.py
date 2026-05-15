#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from contextlib import contextmanager
from pathlib import Path

# Keep zip-distributed repos clean (avoid creating __pycache__/ during harness runs)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.lattice_lib import (
    CaseResult,
    build_text,
    checks_for,
    failed_reasons,
    render_summary_md,
    risk_band,
    risk_score,
    semantic_movement_summary,
    split_csv,
    summarize_failures,
)
from witness.core import WitnessCore
from xyzgl.router import route_turn

MAX_CASES_HARD = 2_500
MAX_CASE_TEXT_CHARS = 220
MAX_CASE_REPLY_CHARS = 800


def _run_id() -> str:
    return make_run_id()


def _clip_text(s: str, *, max_chars: int) -> str:
    t = str(s or "")
    return t if len(t) <= max_chars else t[:max_chars] + "...<truncated>"


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
    p = argparse.ArgumentParser()
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seeds", default="1,1337")
    p.add_argument("--processes", default="SMAW,GMAW")
    p.add_argument("--thicknesses", default="3mm,6mm")
    p.add_argument("--defects", default="uneven fit-up,porosity,undercut")
    p.add_argument("--max-cases", type=int, default=10000, help="Maximum cartesian-product cases")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    seeds = [int(x) for x in split_csv(args.seeds)]
    procs = split_csv(args.processes)
    thks = split_csv(args.thicknesses)
    defects = split_csv(args.defects)
    if not (seeds and procs and thks and defects):
        print("FAIL: lattice lists must be non-empty")
        return 1
    max_cases = min(int(args.max_cases), MAX_CASES_HARD)
    total_cases = len(seeds) * len(procs) * len(thks) * len(defects)
    if total_cases > max_cases:
        print(f"INCOMPLETE: lattice too large ({total_cases} > {max_cases})")
        return 2

    random.seed(seeds[0])
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    wc = WitnessCore()
    cases: list[CaseResult] = []

    try:
        with _env_patch({"GWEN_DISABLED": "1"}):
            idx = 0
            for seed in seeds:
                for proc in procs:
                    for thk in thks:
                        for defect in defects:
                            idx += 1
                            case_id = f"C{idx:03d}"
                            text = build_text(proc, thk, defect)

                            r1 = route_turn(text, seed=seed)
                            cks = checks_for(r1)
                            r2 = route_turn(text, seed=seed)
                            cks["deterministic_same_reply"] = str(r1.get("reply", "")) == str(r2.get("reply", ""))

                            reasons = failed_reasons(cks)
                            risk = risk_score(cks)
                            cases.append(
                                CaseResult(
                                    case_id=case_id,
                                    seed=seed,
                                    process=proc,
                                    thickness=thk,
                                    defect=defect,
                                    text=_clip_text(text, max_chars=MAX_CASE_TEXT_CHARS),
                                    reply=_clip_text(str(r1.get("reply", "")), max_chars=MAX_CASE_REPLY_CHARS),
                                    checks=cks,
                                    ok=len(reasons) == 0,
                                    risk=risk,
                                    band=risk_band(risk),
                                    reasons=reasons,
                                )
                            )

        fx = summarize_failures(cases)
        semantic_summary, case_signatures = semantic_movement_summary(cases)
        suite_failures = list(semantic_summary.get("suite_failures") or [])
        suite_ok = all(c.ok for c in cases) and not suite_failures
        report = {
            "run_id": run_id,
            "issue_id": args.issue,
            "deterministic": True,
            "lattice": {"seeds": seeds, "processes": procs, "thicknesses": thks, "defects": defects},
            "summary": {
                "total_cases": len(cases),
                "case_budget": max_cases,
                "passed": sum(1 for c in cases if c.ok),
                "failed": sum(1 for c in cases if not c.ok),
                "suite_ok": suite_ok,
                "suite_failures": suite_failures,
                "semantic_movement": semantic_summary,
                "band_counts": fx["band_counts"],
                "failure_buckets": fx["failure_buckets"],
            },
            "cases": [
                {
                    "case_id": c.case_id,
                    "seed": c.seed,
                    "process": c.process,
                    "thickness": c.thickness,
                    "defect": c.defect,
                    "text": c.text,
                    "reply": c.reply,
                    "checks": c.checks,
                    "ok": c.ok,
                    "risk": c.risk,
                    "band": c.band,
                    "reasons": c.reasons,
                    "semantic_signature": case_signatures.get(c.case_id, "<missing>"),
                }
                for c in cases
            ],
        }

        event = wc.make_event(args.issue, {"lattice_report": report})
        wc.write_event_json(event, str(run_dir / "lattice_report.json"))
        (run_dir / "lattice_summary.md").write_text(
            render_summary_md(args.issue, run_id, cases, fx, semantic_summary, suite_ok),
            encoding="utf-8",
        )

        run_meta = {
            "run_id": run_id,
            "issue_id": args.issue,
            "deterministic": True,
            "outputs": ["lattice_report.json", "lattice_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        }
        write_json((run_dir / "run.json"), run_meta)

        print(("PASS" if suite_ok else "FAIL") + f": wrote outputs to {run_dir}")
        return 0 if suite_ok else 1

    except Exception as e:
        crash = {"error": repr(e), "run_id": run_id, "issue_id": args.issue}
        write_json((run_dir / "lattice_crash.json"), crash)
        print(f"INCOMPLETE: {e!r}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
