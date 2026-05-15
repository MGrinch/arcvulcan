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


def test_directory_mode_falls_back_from_broken_session_to_valid_turn_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "artifacts"
    report_dir.mkdir()

    (report_dir / "session_report.json").write_text(
        json.dumps(
            {
                "schema_version": "session_report@1",
                "turns": [
                    {
                        "turn_index": 0,
                        "teach": {},
                        "eval": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    turn_report = report_dir / "turn_report.json"
    turn_report.write_text(
        json.dumps(
            {
                "schema_version": "turn_report@1",
                "prompt_meta": {"protocol_regrounded": True},
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            "tools/reground_cadence_verifier.py",
            "--issue",
            "ISSUE-20260315-123",
            "--every",
            "5",
            str(report_dir),
        ],
        tmp_path,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "reground_cadence_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["source"] == str(turn_report)
    assert report["problems"] == []


def test_directory_mode_falls_back_from_wrapped_broken_session_to_valid_turn_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "artifacts_wrapped"
    report_dir.mkdir()

    (report_dir / "session_report.json").write_text(
        json.dumps(
            {
                "schema_version": "witness_bundle@1",
                "payload": {
                    "session_report": {
                        "schema_version": "session_report@1",
                        "turns": [
                            {
                                "turn_index": 0,
                                "teach": {},
                                "eval": {},
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    turn_report = report_dir / "turn_report.json"
    turn_report.write_text(
        json.dumps(
            {
                "schema_version": "turn_report@1",
                "prompt_meta": {"protocol_regrounded": True},
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            "tools/reground_cadence_verifier.py",
            "--issue",
            "ISSUE-20260319-123",
            "--every",
            "5",
            str(report_dir),
        ],
        tmp_path,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "reground_cadence_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["source"] == str(turn_report)
    assert report["problems"] == []
