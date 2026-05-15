from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260318-120"


def _write_run_json(run_dir: Path, outputs: list[str]) -> None:
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": f"{ISSUE_ID}-run",
                "issue_id": ISSUE_ID,
                "seed": 1,
                "deterministic": True,
                "outputs": outputs,
                "exit_codes": {"0": "PASS", "1": "FAIL"},
            }
        ),
        encoding="utf-8",
    )


def _run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/validate_schemas.py", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_schemas_requires_run_json_in_run_directory_mode(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    proc = _run_validate(run_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "missing required run.json" in proc.stdout


@pytest.mark.parametrize("missing_output", ["summary.md", "bundle.zip"])
def test_validate_schemas_fails_when_declared_non_json_output_is_missing(
    tmp_path: Path,
    missing_output: str,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_run_json(run_dir, ["run.json", missing_output])

    proc = _run_validate(run_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"declared output missing: {missing_output}" in proc.stdout


def test_validate_schemas_fails_when_declared_child_run_artifact_is_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_run_json(run_dir, ["run.json", "child_runs/child/run.json"])

    proc = _run_validate(run_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "declared output missing: child_runs/child/run.json" in proc.stdout
