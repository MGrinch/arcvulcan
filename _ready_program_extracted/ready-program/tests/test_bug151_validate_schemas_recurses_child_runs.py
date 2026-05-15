from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")



def test_validate_schemas_fails_for_invalid_nested_child_run_artifact(tmp_path: Path) -> None:
    parent_run = tmp_path / "parent-run"
    child_run = parent_run / "child_runs" / "child-run"

    _write_json(
        parent_run / "run.json",
        {
            "run_id": "parent-run",
            "issue_id": "ISSUE-20260314-151",
            "deterministic": True,
            "outputs": ["run.json", "child_runs/"],
            "exit_codes": {"0": "PASS", "1": "FAIL"},
        },
    )
    _write_json(
        child_run / "run.json",
        {
            "run_id": "child-run",
            "issue_id": "ISSUE-20260314-151",
            "deterministic": True,
            "outputs": ["run.json", "session_report.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL"},
        },
    )
    _write_json(child_run / "session_report.json", {"payload": {}})

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "validate_schemas.py"), str(parent_run)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    combined = proc.stdout + proc.stderr
    assert "child_runs" in combined
    assert "session_report.json" in combined
