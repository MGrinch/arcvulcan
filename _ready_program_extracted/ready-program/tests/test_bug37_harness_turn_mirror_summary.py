from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "tools" / "harness_turn.py"


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    assert candidates, "expected at least one harness_turn run directory"
    return candidates[-1]


def test_harness_turn_summary_includes_mirror_sections_when_present(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS_PATH),
            "--issue",
            "ISSUE-20260315-037",
            "--seed",
            "1337",
            "--text",
            "fit-up is uneven, should I keep tacking?",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DAEDALUS_RUNS_DIR": str(runs_dir),
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_TUTOR_BACKEND": "stub",
            "DAEDALUS_MIRROR_BACKEND": "stub",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dir = _latest_run_dir(runs_dir)
    report = json.loads((run_dir / "turn_report.json").read_text(encoding="utf-8"))
    summary_text = (run_dir / "turn_summary.md").read_text(encoding="utf-8")
    turn_result = report["payload"]["turn_result"]

    mirror_prediction = turn_result.get("mirror_prediction")
    mirror_meta = turn_result.get("mirror_meta")

    assert mirror_prediction, "expected mirror prediction in turn_report.json"
    assert isinstance(mirror_meta, dict) and mirror_meta, "expected mirror metadata in turn_report.json"

    assert "## Mirror Prediction" in summary_text
    assert "## Mirror Metadata" in summary_text
    assert mirror_prediction in summary_text

    expected_meta_json = json.dumps(mirror_meta, ensure_ascii=False, indent=2, sort_keys=True)
    assert expected_meta_json in summary_text
