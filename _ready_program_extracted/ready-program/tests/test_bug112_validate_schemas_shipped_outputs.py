from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260319-112"


def _run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/validate_schemas.py", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_run_json(run_dir: Path, outputs: list[str] | None = None) -> None:
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": f"{ISSUE_ID}-run",
                "issue_id": ISSUE_ID,
                "deterministic": True,
                "outputs": outputs or ["run.json"],
                "exit_codes": {"0": "PASS", "1": "FAIL"},
            }
        ),
        encoding="utf-8",
    )


def test_validate_schemas_accepts_direct_prompt_snapshots_file_without_explicit_schema(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "prompt_snapshots.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "prompt_snapshots@1",
                "generated_at": "2026-03-19T00:00:00Z",
                "cases": {},
            }
        ),
        encoding="utf-8",
    )

    proc = _run_validate(artifact_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS: schemas validated" in proc.stdout


def test_validate_schemas_rejects_invalid_shipped_coverage_raw_in_run_directory_mode(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_run_json(run_dir)
    (run_dir / "coverage_raw.json").write_text("{not-json", encoding="utf-8")

    proc = _run_validate(run_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "coverage_raw.json" in proc.stdout
    assert "coverage_raw.schema.json" in proc.stdout


def test_validate_schemas_rejects_invalid_shipped_lattice_crash_in_run_directory_mode(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_run_json(run_dir)
    (run_dir / "lattice_crash.json").write_text("{not-json", encoding="utf-8")

    proc = _run_validate(run_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "lattice_crash.json" in proc.stdout
    assert "lattice_crash.schema.json" in proc.stdout
