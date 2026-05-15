#!/usr/bin/env python3
from __future__ import annotations

"""Coverage gate (offline). Writes a run bundle and enforces min coverage."""

import argparse
import io
import json
import math
import os
import random
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id
from issue_id import validate_issue_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_id() -> str:
    return make_run_id()


_ENV_KEYS = (
    "DAEDALUS_TUTOR_BACKEND",
    "DAEDALUS_MIRROR_BACKEND",
    "DAEDALUS_ENABLE_MIRROR",
    "DAEDALUS_GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DAEDALUS_GEMINI_MODEL",
    "DAEDALUS_REQUIRE_REAL_BACKENDS",
    "DAEDALUS_GROUNDING_MODE",
    "DAEDALUS_PROTOCOL_PATH",
)


def _clear_env() -> None:
    for k in _ENV_KEYS:
        os.environ.pop(k, None)


def _call_tool_main(mod, argv: list[str]) -> int:
    """Call a tools.* module's `main()` without argv bleed or stdout bleed."""
    old_argv = sys.argv[:]
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        sys.argv = [Path(getattr(mod, "__file__", "tool")).name] + list(argv)
        try:
            with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                rc = mod.main()
        except SystemExit as e:
            rc = int(getattr(e, "code", 0) or 0)
        return int(rc or 0)
    finally:
        sys.argv = old_argv


def _classify_gate_result(*, line_pct: float, branch_pct: float, min_line: float, min_branch: float, smoke_failures: list[str]) -> tuple[bool, str, str, list[str]]:
    reasons: list[str] = []
    if line_pct < min_line:
        reasons.append("line_threshold")
    if branch_pct < min_branch:
        reasons.append("branch_threshold")
    if smoke_failures:
        reasons.append("smoke_regression")
    ok = not reasons
    if ok:
        return True, "PASS", "PASS: thresholds met; smoke suite clean", reasons
    if reasons == ["smoke_regression"]:
        return False, "FAIL_SMOKE", f"FAIL: smoke regressions; smoke_failures={','.join(smoke_failures)}", reasons
    if "smoke_regression" not in reasons:
        missed: list[str] = []
        if line_pct < min_line:
            missed.append("line")
        if branch_pct < min_branch:
            missed.append("branch")
        return False, "FAIL_THRESHOLDS", "FAIL: coverage thresholds not met; missing=" + ",".join(missed), reasons
    missed = []
    if line_pct < min_line:
        missed.append("line")
    if branch_pct < min_branch:
        missed.append("branch")
    return (
        False,
        "FAIL_THRESHOLDS_AND_SMOKE",
        "FAIL: coverage thresholds not met and smoke regressions present; missing=" + ",".join(missed) + f"; smoke_failures={','.join(smoke_failures)}",
        reasons,
    )


def main() -> int:
    p = argparse.ArgumentParser(prog="coverage_gate")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--min-line", type=float, default=35.0)
    p.add_argument("--min-branch", type=float, default=5.0)
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    try:
        min_line = float(args.min_line)
        min_branch = float(args.min_branch)
    except Exception:
        print("INCOMPLETE: invalid threshold values")
        return 2
    if not (math.isfinite(min_line) and math.isfinite(min_branch)):
        print("INCOMPLETE: thresholds must be finite numbers")
        return 2
    if not (0.0 <= min_line <= 100.0 and 0.0 <= min_branch <= 100.0):
        print("INCOMPLETE: thresholds must be between 0 and 100")
        return 2

    try:
        import coverage  # type: ignore
    except Exception:
        print("INCOMPLETE: python package 'coverage' not installed")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    _clear_env()

    cov = coverage.Coverage(branch=True, source=[str(_REPO_ROOT / "xyzgl")], data_file=str(run_dir / ".coverage"))
    cov.start()

    # --- smoke suite (deterministic, network-free) ---
    from xyzgl.router import route_turn

    _ = route_turn("coverage_gate", seed=args.seed)

    import tools.repro_backends_smoke as rb
    import tools.repro_grounding_protocol_smoke as rg
    import tools.repro_session_smoke as rs

    # Keep child run bundles nested under this run.
    child_runs = run_dir / "child_runs"
    child_runs.mkdir(parents=True, exist_ok=True)
    old_runs = os.environ.get("DAEDALUS_RUNS_DIR")
    os.environ["DAEDALUS_RUNS_DIR"] = str(child_runs)

    smoke_failures: list[str] = []
    try:
        if _call_tool_main(rb, ["--issue", args.issue, "--seed", str(args.seed)]) != 0:
            smoke_failures.append("repro_backends_smoke")
        if _call_tool_main(rg, ["--issue", args.issue, "--seed", str(args.seed)]) != 0:
            smoke_failures.append("repro_grounding_protocol_smoke")
        if _call_tool_main(rs, ["--issue", args.issue, "--seed", str(args.seed)]) != 0:
            smoke_failures.append("repro_session_smoke")
    finally:
        if old_runs is None:
            os.environ.pop("DAEDALUS_RUNS_DIR", None)
        else:
            os.environ["DAEDALUS_RUNS_DIR"] = old_runs

    # Cover orchestrator path.
    from xyzgl.config import XYZGLConfig
    from xyzgl.knowledge.graph import default_graph
    from xyzgl.orchestrator.session_loop import run_session

    cfg = XYZGLConfig()

    def _input_provider(_prompt: str):
        return ("idk. uneven fit-up causes weak toes and lack of fusion.", {"typing_ms": 4000})

    _rep, _g = run_session(session_id="COV", cfg=cfg, seed=args.seed, max_turns=3, graph=default_graph(), input_provider=_input_provider)

    cov.stop()

    raw_path = run_dir / "coverage_raw.json"
    cov.json_report(outfile=str(raw_path))
    with raw_path.open("r", encoding="utf-8", errors="replace") as f:
        raw = json.load(f)
    # coverage.py chooses its own pretty-printing layout; rewrite the emitted raw
    # report through the repo's canonical JSON writer so strict round-trip checks
    # do not flag coverage_raw.json as unstable immediately after a green run.
    write_json(raw_path, raw)
    totals = raw.get("totals") or {}

    line_pct = float(totals.get("percent_covered") or 0.0)
    nb = int(totals.get("num_branches") or 0)
    cb = int(totals.get("covered_branches") or 0)
    branch_pct = (cb / nb * 100.0) if nb else 0.0

    line_pct_report = round(line_pct, 4)
    branch_pct_report = round(branch_pct, 4)
    ok, status, status_line, failure_reasons = _classify_gate_result(
        line_pct=line_pct_report,
        branch_pct=branch_pct_report,
        min_line=min_line,
        min_branch=min_branch,
        smoke_failures=smoke_failures,
    )

    report = {
        "schema_version": "coverage_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "status": status,
        "failure_reasons": failure_reasons,
        "smoke_failures": smoke_failures,
        "line_percent": line_pct_report,
        "branch_percent": branch_pct_report,
        "min_line": min_line,
        "min_branch": min_branch,
        "raw": {
            "num_statements": int(totals.get("num_statements") or 0),
            "covered_lines": int(totals.get("covered_lines") or 0),
            "num_branches": nb,
            "covered_branches": cb,
            "missing_lines": int(totals.get("missing_lines") or 0),
            "missing_branches": int(totals.get("missing_branches") or 0),
        },
    }
    write_json((run_dir / "coverage_report.json"), report)
    (run_dir / "coverage_summary.md").write_text(
        "# Coverage Gate Summary\n\n"
        f"- issue: `{args.issue}`\n"
        f"- run_id: `{run_id}`\n"
        f"- line%: `{round(line_pct, 2)}` (min {min_line})\n"
        f"- branch%: `{round(branch_pct, 2)}` (min {min_branch})\n\n"
        f"{status_line}\n",
        encoding="utf-8",
    )

    outputs = ["coverage_report.json", "coverage_summary.md", "coverage_raw.json", "child_runs/", "run.json"]
    if (run_dir / ".coverage").exists():
        outputs.insert(0, ".coverage")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": False,
        "artifact_identity_stable": False,
        "artifact_content_stable": False,
        "determinism_basis": "coverage data and smoke child runs may vary across executions, and the default run directory id is unpredictable",
        "outputs": outputs,
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(f"{status}: wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
