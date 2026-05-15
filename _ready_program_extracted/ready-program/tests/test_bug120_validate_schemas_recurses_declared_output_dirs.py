from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_validate_schemas_fails_for_invalid_nested_declared_child_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_dir = tmp_path / "run"
    child_dir = run_dir / "child_runs" / "child"
    child_dir.mkdir(parents=True)

    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "ISSUE-20260315-120-parent",
                "issue_id": "ISSUE-20260315-120",
                "seed": 1,
                "deterministic": True,
                "outputs": ["run.json", "child_runs/"],
                "exit_codes": {"0": "PASS", "1": "FAIL"},
            }
        ),
        encoding="utf-8",
    )
    (child_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "ISSUE-20260315-120-child",
                "issue_id": "ISSUE-20260315-120",
                "seed": 1,
                "deterministic": True,
                "outputs": ["run.json", "coverage_report.json"],
                "exit_codes": {"0": "PASS", "1": "FAIL"},
            }
        ),
        encoding="utf-8",
    )
    (child_dir / "coverage_report.json").write_text(
        json.dumps({"schema_version": "coverage_report@1", "oops": True}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "tools/validate_schemas.py", str(run_dir)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "coverage_report.json" in proc.stdout
    assert "coverage_report.schema.json" in proc.stdout
