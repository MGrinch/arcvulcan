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


def test_reground_cadence_accepts_standalone_session_report_json(tmp_path: Path) -> None:
    session_report = tmp_path / "session_report.json"
    session_report.write_text(
        json.dumps(
            {
                "schema_version": "session_report@1",
                "turns": [
                    {
                        "turn_index": 0,
                        "teach": {"prompt_meta": {"protocol_regrounded": True}},
                        "eval": {"prompt_meta": {"protocol_regrounded": True}},
                    },
                    {
                        "turn_index": 1,
                        "teach": {"prompt_meta": {"protocol_regrounded": False}},
                        "eval": {"prompt_meta": {"protocol_regrounded": False}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            "tools/reground_cadence_verifier.py",
            "--issue",
            "ISSUE-20260314-142",
            "--every",
            "5",
            str(session_report),
        ],
        tmp_path,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "reground_cadence_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["source"] == str(session_report)
    assert report["problems"] == []


def test_reground_cadence_accepts_standalone_session_report_with_noncanonical_filename(tmp_path: Path) -> None:
    standalone_report = tmp_path / "normalized_payload.json"
    standalone_report.write_text(
        json.dumps(
            {
                "schema_version": "session_report@1",
                "turns": [
                    {
                        "turn_index": 0,
                        "teach": {"prompt_meta": {"protocol_regrounded": True}},
                        "eval": {"prompt_meta": {"protocol_regrounded": True}},
                    },
                    {
                        "turn_index": 1,
                        "teach": {"prompt_meta": {"protocol_regrounded": False}},
                        "eval": {"prompt_meta": {"protocol_regrounded": False}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = _run(
        [
            "tools/reground_cadence_verifier.py",
            "--issue",
            "ISSUE-20260318-142",
            "--every",
            "5",
            str(standalone_report),
        ],
        tmp_path,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "reground_cadence_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["source"] == str(standalone_report)
    assert report["problems"] == []
