#!/usr/bin/env python3
from __future__ import annotations

"""CI Gate (local).

Runs a small, deterministic battery of checks and harnesses.

Exit codes:
  0 PASS
  1 FAIL
  2 INCOMPLETE
"""

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_RUN_RE = re.compile(r"wrote outputs to (?P<path>.+)$")
_MAX_STEP_LOG_BYTES = 64 * 1024
_MAX_CMD_ARG_CHARS = 4096
_MAX_STEP_TIMEOUT_S = 900
_SAFE_ARG_RE = re.compile(r"^[^\x00\r\n]*$")
_ABS_PATH_RE = re.compile(r"(?i)(?:[A-Z]:\\|/)[^\s]+")
_MIRROR_CALIBRATION_MIN_AVG = "0.35"


def _run_id() -> str:
    return make_run_id()


def _tail(s: str, n: int = 900) -> str:
    s = s or ""
    return s if len(s) <= n else ("..." + s[-n:])


def _tail_file_text(path: Path, *, max_bytes: int) -> str:
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start, os.SEEK_SET)
        data = f.read(max_bytes)
    txt = data.decode("utf-8", errors="replace")
    return ("..." + txt) if size > max_bytes else txt


def _sanitize_tail_text(text: str) -> str:
    return _ABS_PATH_RE.sub("<path>", text or "")


def _safe_step_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())[:64] or "step"


def _is_safe_cmd(cmd: list[str]) -> bool:
    if not cmd:
        return False
    for part in cmd:
        p = str(part or "")
        if not p or len(p) > _MAX_CMD_ARG_CHARS or not _SAFE_ARG_RE.fullmatch(p):
            return False
    return True


def _run_step(
    name: str,
    cmd: list[str],
    env: dict[str, str],
    *,
    timeout_s: int,
    run_dir: Path,
) -> tuple[int, str, str]:
    if not _is_safe_cmd(cmd):
        raw = _tail("unsafe subprocess arguments rejected")
        return 1, raw, raw
    timeout_s = max(1, min(int(timeout_s), _MAX_STEP_TIMEOUT_S))
    step_slug = _safe_step_name(name)
    log_file = run_dir / f".ci_gate_{step_slug}_{os.getpid()}_{secrets.token_hex(4)}.log"
    try:
        with log_file.open("xb") as logf:
            p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, env=env)
            try:
                rc = int(p.wait(timeout=timeout_s))
            except subprocess.TimeoutExpired as e:
                p.kill()
                p.wait(timeout=5)
                out = _tail_file_text(log_file, max_bytes=_MAX_STEP_LOG_BYTES)
                raw = _tail(f"{name} timed out after {timeout_s}s: {e}\n{out}", n=2000)
                return 1, raw, _tail(_sanitize_tail_text(raw), n=2000)
        out = _tail_file_text(log_file, max_bytes=_MAX_STEP_LOG_BYTES)
        raw = _tail(out, n=2000)
        return rc, raw, _tail(_sanitize_tail_text(raw), n=2000)
    except Exception as e:
        raw = _tail(f"{name} execution error: {type(e).__name__}: {e}")
        return 1, raw, _tail(_sanitize_tail_text(raw))
    finally:
        if log_file.exists():
            try:
                log_file.unlink()
            except OSError:
                pass

def _extract_run_dir(stdout_tail: str, expected_root: Path) -> Path | None:
    lines = (stdout_tail or "").strip().splitlines()
    if lines:
        for ln in reversed(lines):
            m = _RUN_RE.search(ln.strip())
            if not m:
                continue
            p = Path(m.group("path"))
            try:
                p_resolved = p.resolve()
                p_resolved.relative_to(expected_root.resolve())
                return p_resolved
            except Exception:
                continue
    try:
        child_candidates = sorted(
            (
                child.resolve()
                for child in expected_root.iterdir()
                if child.is_dir() and (child / "run.json").is_file()
            ),
            key=lambda p: p.name,
        )
    except Exception:
        child_candidates = []
    return child_candidates[-1] if child_candidates else None


def _rel_to(base: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(base.resolve())).replace("\\", "/")
    except Exception:
        return p.name


def main() -> int:
    p = argparse.ArgumentParser(prog="ci_gate")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--max-turns", type=int, default=6)
    p.add_argument("--step-timeout", type=int, default=120, help="max seconds per subprocess step")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    py = sys.executable
    child_runs = (run_dir / "child_runs").resolve()
    child_runs.mkdir(parents=True, exist_ok=True)
    step_env = dict(os.environ)
    step_env["DAEDALUS_RUNS_DIR"] = str(child_runs)

    steps: list[dict] = []
    overall = "PASS"

    def add_step(name: str, cmd: list[str]) -> tuple[int, str, str]:
        nonlocal overall
        code, raw_out, sanitized_out = _run_step(
            name,
            cmd,
            step_env,
            timeout_s=max(1, int(args.step_timeout)),
            run_dir=run_dir,
        )
        steps.append({"name": name, "exit_code": code, "stdout_tail": sanitized_out})
        if code == 1:
            overall = "FAIL"
        elif code == 2 and overall != "FAIL":
            overall = "INCOMPLETE"
        return code, raw_out, sanitized_out

    # 1) Repo sanity
    add_step("doctor", [py, "tools/doctor.py"])
    add_step("selfcheck", [py, "tools/selfcheck.py"])

    # 1b) Fast regression nets (repo-level)
    add_step("secret_scanner", [py, "tools/secret_scanner.py", "--issue", args.issue, "--enforce"])
    add_step("prompt_snapshot_guard", [py, "tools/prompt_snapshot_guard.py", "--issue", args.issue])

    # 2) Backend contract (no network)
    add_step("backend_contract_probe", [py, "tools/backend_contract_probe.py", "--issue", args.issue, "--seed", str(args.seed)])

    # 2b) Timing smoke (no network)
    add_step("stage_timing_profiler", [py, "tools/stage_timing_profiler.py", "--issue", args.issue])

    # 3) Orchestrated session harness (stub)
    _, raw_out, _ = add_step(
        "harness_session",
        [
            py,
            "tools/harness_session.py",
            "--issue",
            args.issue,
            "--seed",
            str(args.seed),
            "--max-turns",
            str(args.max_turns),
            "--protocol-reground-every",
            "5",
            "--enable-mirror",
            "--grounding",
        ],
    )
    session_dir = _extract_run_dir(raw_out, expected_root=child_runs)

    # 4) Run-dir based checks
    if session_dir and session_dir.exists():
        add_step("validate_schemas", [py, "tools/validate_schemas.py", str(session_dir)])
        add_step("graph_invariant_checker", [py, "tools/graph_invariant_checker.py", "--issue", args.issue, str(session_dir)])
        add_step("reground_cadence_verifier", [py, "tools/reground_cadence_verifier.py", "--issue", args.issue, "--every", "5", str(session_dir)])
        add_step("repro_replay_diff", [py, "tools/repro_replay_diff.py", "--issue", args.issue, str(session_dir)])
        add_step("protocol_drift_radar", [py, "tools/protocol_drift_radar.py", "--issue", args.issue, str(session_dir)])
        add_step("mirror_leakage_detector", [py, "tools/mirror_leakage_detector.py", "--issue", args.issue, str(session_dir)])
        add_step("mirror_calibration_bench", [py, "tools/mirror_calibration_bench.py", "--issue", args.issue, "--min-avg", _MIRROR_CALIBRATION_MIN_AVG, str(session_dir)])
        add_step(
            "ontario_claims_citation_guard",
            [py, "tools/ontario_claims_citation_guard.py", "--issue", args.issue, "--enforce", str(session_dir)],
        )

        # Security regression checks (stub-safe)
        add_step("redteam_injection_suite", [py, "tools/redteam_injection_suite.py", "--issue", args.issue])
        add_step("redteam_rag_poisoning_suite", [py, "tools/redteam_rag_poisoning_suite.py", "--issue", args.issue])
        add_step("property_turn_fuzzer", [py, "tools/property_turn_fuzzer.py", "--issue", args.issue, "--cases", "80"])
    else:
        steps.append({"name": "session_run_dir", "exit_code": 2, "stdout_tail": "INCOMPLETE: could not locate session run dir"})
        if overall != "FAIL":
            overall = "INCOMPLETE"

    report = {
        "schema_version": "ci_gate_report@1",
        "tool": "ci_gate",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "overall": overall,
        "child_runs_dir": _rel_to(run_dir, child_runs),
        "steps": steps,
    }
    write_json((run_dir / "ci_gate_report.json"), report)
    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "deterministic": False,
            "outputs": ["ci_gate_report.json", "ci_gate_summary.md", "child_runs/", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    # Human-friendly summary (non-schema artifact)
    summary_lines: list[str] = []
    summary_lines.append(f"# CI Gate Summary - {overall}")
    summary_lines.append("")
    summary_lines.append(f"- issue: {args.issue}")
    summary_lines.append(f"- run_id: {run_id}")
    summary_lines.append(f"- seed: {args.seed}")
    if session_dir:
        summary_lines.append(f"- session_dir: {_rel_to(run_dir, session_dir)}")
    summary_lines.append("")
    summary_lines.append("## Steps")
    for st in steps:
        nm = st.get("name")
        code = st.get("exit_code")
        summary_lines.append(f"- **{nm}**: `{code}`")
    (run_dir / "ci_gate_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"{overall}: wrote outputs to {run_dir}")
    return 1 if overall == "FAIL" else (2 if overall == "INCOMPLETE" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
