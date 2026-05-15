from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _extract_run_dir(stdout: str) -> Path:
    match = re.search(r"wrote outputs to (.+)$", stdout.strip())
    assert match, stdout
    return Path(match.group(1).strip())


def test_selfcheck_issue_mode_writes_standard_run_bundle(tmp_path: Path) -> None:
    proc = _run(["tools/selfcheck.py", "--issue", "ISSUE-20260314-022", "--seed", "7"], tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "selfcheck_report.json").read_text(encoding="utf-8"))
    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["issue_id"] == "ISSUE-20260314-022"
    assert report["seed"] == 7
    assert {check["name"] for check in report["checks"]} == {"baseline_router_shape", "bounded_io_contract"}
    assert run_meta["outputs"] == ["selfcheck_report.json", "selfcheck_summary.md", "run.json"]


def test_builtin_mutation_suite_tracks_current_router_anchors(tmp_path: Path) -> None:
    proc = _run(["tools/mutation_suite.py", "--issue", "ISSUE-20260314-022", "--engine", "builtin", "--target", "xyzgl"], tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "mutation_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["problems"] == []
    assert report["builtin_results"]["killed"] == 3
    assert report["builtin_results"]["survived"] == 0
    assert [m["id"] for m in report["builtin_results"]["mutants"]] == ["MUT-001", "MUT-002", "MUT-003"]
    assert all(m["status"] == "KILLED" for m in report["builtin_results"]["mutants"])
