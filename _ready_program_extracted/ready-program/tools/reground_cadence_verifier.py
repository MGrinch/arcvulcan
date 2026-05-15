#!/usr/bin/env python3
from __future__ import annotations

"""Verify protocol re-ground cadence.

Checks that ROLE_PROTOCOL is re-injected on turn 0 and then every N turns.
Reads:
  - runs/<run_id>/session_report.json (preferred)
  - runs/<run_id>/turn_report.json

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id
from issue_id import validate_issue_id


def _run_id() -> str:
    return make_run_id()


def _load_json(p: Path) -> dict:
    try:
        out = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_pairs)
    except Exception:
        return {}
    return out if isinstance(out, dict) else {}


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _extract_session_turns(doc: dict) -> list[dict] | None:
    sr = None
    if doc.get("schema_version") == "session_report@1":
        sr = doc
    else:
        payload = doc.get("payload") or {}
        candidate = payload.get("session_report")
        if isinstance(candidate, dict):
            sr = candidate
    if not isinstance(sr, dict):
        return None
    turns = sr.get("turns")
    return turns if isinstance(turns, list) else None


def _extract_turn_prompt_meta(doc: dict) -> dict | None:
    tr = None
    if doc.get("schema_version") == "turn_report@1":
        tr = doc
    else:
        payload = doc.get("payload") or {}
        candidate = payload.get("turn_result")
        if isinstance(candidate, dict):
            tr = candidate
    if not isinstance(tr, dict):
        return None
    pm = tr.get("prompt_meta")
    return pm if isinstance(pm, dict) else None


def _session_has_usable_prompt_meta(turns: list[dict]) -> bool:
    for tr in turns:
        teach_pm = ((tr.get("teach") or {}).get("prompt_meta"))
        eval_pm = ((tr.get("eval") or {}).get("prompt_meta"))
        if isinstance(teach_pm, dict) and isinstance(eval_pm, dict):
            return True
    return False


def _choose_report(target: Path) -> tuple[Path | None, dict, list[dict] | None, dict | None]:
    candidates: list[Path] = []
    if target.is_dir():
        for name in ("session_report.json", "turn_report.json"):
            candidate = target / name
            if candidate.exists():
                candidates.append(candidate)
    elif target.exists():
        candidates.append(target)

    fallback_path: Path | None = None
    fallback_doc: dict = {}
    for candidate in candidates:
        doc = _load_json(candidate)
        turns = _extract_session_turns(doc)
        if turns is not None:
            if _session_has_usable_prompt_meta(turns):
                return candidate, doc, turns, None
            if fallback_path is None:
                fallback_path = candidate
                fallback_doc = doc
            continue
        pm = _extract_turn_prompt_meta(doc)
        if pm is not None:
            return candidate, doc, None, pm
        if fallback_path is None:
            fallback_path = candidate
            fallback_doc = doc
    return fallback_path, fallback_doc, None, None


def _expected(turn_index: int, every: int) -> bool:
    if every <= 0:
        return turn_index == 0
    return turn_index == 0 or (turn_index % every == 0)


def _write_bundle(out_dir: Path, *, run_id: str, issue: str, seed: int | None, overall: str, source: str | None, checks: int, problems: int) -> None:
    write_json(
        out_dir / "run.json",
        {
            "run_id": run_id,
            "issue_id": issue,
            "seed": seed,
            "deterministic": True,
            "outputs": ["reground_cadence_report.json", "reground_cadence_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )
    (out_dir / "reground_cadence_summary.md").write_text(
        "\n".join(
            [
                f"# Reground Cadence Summary — {overall}",
                "",
                f"- issue: {issue}",
                f"- run_id: {run_id}",
                f"- source: {source or ''}",
                f"- checks: {checks}",
                f"- problems: {problems}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(prog="reground_cadence_verifier")
    ap.add_argument("path", help="runs/<run_id>/ dir or a report JSON")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--every", type=int, default=5, help="Re-ground every N turns (0 disables periodic)")
    ap.add_argument("--strict", action="store_true", help="Fail if any prompt_meta is missing")
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    target = Path(args.path)
    if not target.exists():
        print(f"FAIL: not found: {target}")
        return 1

    run_id = _run_id()
    out_dir = allocate_run_dir(run_id)
    report_path, doc, selected_turns, selected_prompt_meta = _choose_report(target)

    checks: list[dict] = []
    problems: list[str] = []
    details: str | None = None
    overall = "PASS"
    exit_code = 0

    if report_path is None or not report_path.exists():
        overall = "INCOMPLETE"
        exit_code = 2
        details = "no session_report.json or turn_report.json found"
    else:
        turns = selected_turns
        if turns is not None:
            for tr in turns:
                ti = int(tr.get("turn_index", -1))
                teach_pm = ((tr.get("teach") or {}).get("prompt_meta") or {})
                eval_pm = ((tr.get("eval") or {}).get("prompt_meta") or {})
                if not isinstance(teach_pm, dict) or not isinstance(eval_pm, dict):
                    if args.strict:
                        problems.append(f"turn {ti}: missing prompt_meta")
                    checks.append({"turn_index": ti, "expected": _expected(ti, args.every), "observed": None})
                    continue
                teach_obs = bool(teach_pm.get("protocol_regrounded"))
                eval_obs = bool(eval_pm.get("protocol_regrounded"))
                exp = _expected(ti, args.every)
                ok = (teach_obs == exp) and (eval_obs == exp)
                checks.append({"turn_index": ti, "expected": exp, "observed": {"teach": teach_obs, "eval": eval_obs}, "pass": ok})
                if not ok:
                    problems.append(f"turn {ti}: expected {exp}, got teach={teach_obs}, eval={eval_obs}")
        else:
            pm = selected_prompt_meta
            if pm is None:
                problems.append("could not extract prompt_meta")
            else:
                obs = bool(pm.get("protocol_regrounded"))
                exp = _expected(0, args.every)
                ok = obs == exp
                checks.append({"turn_index": 0, "expected": exp, "observed": obs, "pass": ok})
                if not ok:
                    problems.append(f"turn 0: expected {exp}, got {obs}")

        overall = "PASS" if not problems else "FAIL"
        exit_code = 0 if overall == "PASS" else 1

    report = {
        "schema_version": "reground_cadence_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "every": args.every,
        "source": str(report_path) if report_path else None,
        "overall": overall,
        "checks": checks,
        "problems": problems,
    }
    if details:
        report["details"] = details
    write_json((out_dir / "reground_cadence_report.json"), report)
    _write_bundle(
        out_dir,
        run_id=run_id,
        issue=args.issue,
        seed=None,
        overall=overall,
        source=str(report_path) if report_path else None,
        checks=len(checks),
        problems=len(problems),
    )

    print(f"{overall}: wrote outputs to {out_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
