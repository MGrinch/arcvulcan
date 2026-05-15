from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260315-078"


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _latest_run(root: Path) -> Path:
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    assert runs, "expected a run bundle"
    return runs[-1]


def test_coverage_gate_emits_canonical_coverage_raw(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path)

    gate = _run([sys.executable, "tools/coverage_gate.py", "--issue", ISSUE_ID, "--seed", "1337"], env=env)
    assert gate.returncode == 0, gate.stdout + gate.stderr

    run_dir = _latest_run(tmp_path)
    strict = _run([sys.executable, "tools/artifact_roundtrip.py", "--issue", ISSUE_ID, "--strict", str(run_dir)], env=env)
    assert strict.returncode == 0, strict.stdout + strict.stderr

    strict_run_dir = _latest_run(tmp_path)
    report = json.loads((strict_run_dir / "artifact_roundtrip_report.json").read_text(encoding="utf-8"))
    changed = {Path(row["file"]).name: row for row in report["files"] if row.get("changed")}
    assert "coverage_raw.json" not in changed, report
