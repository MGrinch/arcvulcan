#!/usr/bin/env python3
from __future__ import annotations

"""Mutation testing wrapper.

Out of the box, this tool runs a tiny deterministic *builtin* mutation suite against
the canonical interaction surface (router) to detect obvious test weakness.

Optional: install and use a real engine (cosmic-ray) for deeper mutation testing.

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

import argparse
import importlib.util
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_SUBPROCESS_TIMEOUT_S = 120
_OPTIONAL_MODULE_ALLOWLIST = {"cosmic_ray"}
_SUPPORTED_TARGETS_BY_ENGINE = {
    "builtin": {"xyzgl"},
    "cosmic-ray": {"xyzgl"},
}

def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"

def _tail(s: str, n: int = 900) -> str:
    s = s or ""
    return s if len(s) <= n else ("…" + s[-n:])

def _has_module(name: str) -> bool:
    if str(name or "") not in _OPTIONAL_MODULE_ALLOWLIST:
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False

def _run_cmd_capture(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return int(p.returncode), _tail(out)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + ("\n" + e.stderr if e.stderr else "")
        return 124, _tail(f"timeout after {_SUBPROCESS_TIMEOUT_S}s\n{out}")

def _builtin_router_mutations() -> list[dict]:
    return [
        {
            "id": "MUT-001",
            "file": "xyzgl/router.py",
            "find": "reply = _format_tutor_reply(tutor_res.text, limit=out_limit)",
            "repl": "reply = \"unsafe mutant reply\"  # MUT-001\n",
        },
        {
            "id": "MUT-002",
            "file": "xyzgl/router.py",
            "find": "text_in = normalize_and_clamp_user_text(user_text, max_chars=in_limit)",
            "repl": "text_in = user_text  # MUT-002\n",
        },
        {
            "id": "MUT-003",
            "file": "xyzgl/router.py",
            "find": '"input_routed": text_in,',
            "repl": '"input_routed": "",  # MUT-003\n',
        },
    ]

def main() -> int:
    p = argparse.ArgumentParser(prog="mutation_suite")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--engine", choices=["builtin", "cosmic-ray"], default="builtin")
    p.add_argument("--target", default="xyzgl", help="builtin supports only 'xyzgl'")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2
    supported_targets = _SUPPORTED_TARGETS_BY_ENGINE.get(args.engine, set())
    if args.target not in supported_targets:
        allowed = ", ".join(sorted(supported_targets)) or "<none>"
        print(f"INCOMPLETE: --engine {args.engine} supports only --target values: {allowed}")
        return 2

    random.seed(1337)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)

    overall, problems, details, cmd = "PASS", [], [], []
    builtin_results = None

    if args.engine == "cosmic-ray":
        if not _has_module("cosmic_ray"):
            overall = "INCOMPLETE"
            details += ["cosmic-ray is not installed", "Install: pip install cosmic-ray"]
        else:
            cmd = [sys.executable, "-m", "cosmic_ray", "--help"]
            if args.dry_run:
                details.append("DRY-RUN: " + " ".join(cmd))
            else:
                rc, out = _run_cmd_capture(cmd)
                if rc != 0:
                    overall = "FAIL"
                    problems.append(f"cosmic-ray returned {rc}")
                    details.append("stdout_tail: " + out)
                else:
                    details.append("cosmic-ray is installed and runnable")
    else:
        killed = survived = 0
        results: list[dict] = []
        for m in _builtin_router_mutations():
            fpath = _REPO_ROOT / m["file"]
            original = fpath.read_text(encoding="utf-8")
            if m["find"] not in original:
                overall = "FAIL"
                problems.append(f"mutation pattern not found: {m['id']}")
                continue
            mutated = original.replace(m["find"], m["repl"], 1)
            if args.dry_run:
                results.append({"id": m["id"], "status": "DRY-RUN"})
                continue

            fpath.write_text(mutated, encoding="utf-8")
            try:
                rc, oracle_tail = _run_cmd_capture([sys.executable, "tools/selfcheck.py"])
            finally:
                fpath.write_text(original, encoding="utf-8")

            if rc != 0:
                killed += 1
                results.append({"id": m["id"], "status": "KILLED", "rc": rc, "oracle_output_tail": oracle_tail})
            else:
                survived += 1
                results.append({"id": m["id"], "status": "SURVIVED", "rc": rc})

        cmd = [sys.executable, "tools/selfcheck.py"]
        if args.dry_run:
            details.append("DRY-RUN: builtin mutations listed")
        else:
            details.append(f"killed={killed} survived={survived}")
            if survived > 0:
                overall = "FAIL"
        details.append("builtin suite uses tools/selfcheck.py as the test oracle (captured, not printed)")
        builtin_results = {"killed": killed, "survived": survived, "mutants": results}

    report = {
        "schema_version": "mutation_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "engine": args.engine,
        "target": args.target,
        "overall": overall,
        "command": cmd,
        "problems": problems,
        "details": details,
    }
    if args.engine == "builtin":
        report["builtin_results"] = builtin_results if not args.dry_run else {"mutants": _builtin_router_mutations()}

    write_json((run_dir / "mutation_report.json"), report)

    summary = [
        "# Mutation Suite Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- engine: `{args.engine}`",
        f"- target: `{args.target}`",
        f"- overall: **{overall}**",
        "",
    ]
    if cmd:
        summary += ["## Command", "", "```", " ".join(cmd), "```", ""]
    if problems:
        summary += ["## Problems", *[f"- {x}" for x in problems], ""]
    if details:
        summary += ["## Details", *[f"- {x}" for x in details], ""]

    (run_dir / "mutation_summary.md").write_text("\n".join(summary), encoding="utf-8")
    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
                "deterministic": True,
            "outputs": ["mutation_report.json", "mutation_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    print(f"{overall}: wrote outputs to {run_dir}")
    return 1 if overall == "FAIL" else (2 if overall == "INCOMPLETE" else 0)

if __name__ == "__main__":
    raise SystemExit(main())
