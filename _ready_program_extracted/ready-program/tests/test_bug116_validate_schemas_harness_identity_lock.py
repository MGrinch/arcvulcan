from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260319-116"
EVENT_ID = "EVT-0123456789ab"
CREATED_AT = "1970-01-01T00:00:00Z"


def _run_validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/validate_schemas.py", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        (
            "session_report.json",
            {
                "session_report": {
                    "schema_version": "session_report@1",
                    "session_id": "session-1",
                    "max_turns": 1,
                    "turns": [],
                }
            },
        ),
        (
            "turn_report.json",
            {
                "turn_result": {
                    "config": {},
                    "input": "question",
                    "seed": 1,
                    "reply": "answer",
                    "backend": "stub",
                }
            },
        ),
        (
            "lattice_report.json",
            {
                "lattice_report": {
                    "issue_id": ISSUE_ID,
                    "run_id": "run-1",
                    "cases": [],
                }
            },
        ),
    ],
)
def test_validate_schemas_rejects_primary_harness_reports_that_still_declare_witness_event(
    tmp_path: Path,
    filename: str,
    payload: dict,
) -> None:
    artifact_path = tmp_path / filename
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "witness_event@1",
                "event_id": EVENT_ID,
                "issue_id": ISSUE_ID,
                "created_at": CREATED_AT,
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_validate(artifact_path)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "schema_version mismatch" in combined
    assert "witness_event@1" in combined


@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("session_report.witness.json", {"session_report": {"schema_version": "session_report@1"}}),
        ("turn_report.witness.json", {"turn_result": {"schema_version": "turn_report@1"}}),
        ("lattice_report.witness.json", {"lattice_report": {"schema_version": "lattice_report@1"}}),
    ],
)
def test_validate_schemas_accepts_explicit_witness_sidecar_names(
    tmp_path: Path,
    filename: str,
    payload: dict,
) -> None:
    artifact_path = tmp_path / filename
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "witness_event@1",
                "event_id": EVENT_ID,
                "issue_id": ISSUE_ID,
                "created_at": CREATED_AT,
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_validate(artifact_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS: schemas validated" in proc.stdout
