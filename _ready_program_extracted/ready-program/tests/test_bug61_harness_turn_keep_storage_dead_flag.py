from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "tools" / "harness_turn.py"


def test_harness_turn_help_does_not_advertise_removed_keep_storage_flag() -> None:
    proc = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--help"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--keep-storage" not in proc.stdout


def test_harness_turn_rejects_removed_keep_storage_flag(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS_PATH),
            "--issue",
            "ISSUE-20260315-061",
            "--keep-storage",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)},
        capture_output=True,
        text=True,
        check=False,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2, combined
    assert "unrecognized arguments: --keep-storage" in combined
    assert not runs_dir.exists()
