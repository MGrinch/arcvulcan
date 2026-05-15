from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260319-101"


def _run(tool_rel: str, args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / tool_rel), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("tool_rel", "args", "expected_stdout"),
    [
        (
            "tools/seed_sweep.py",
            ["--issue", ISSUE_ID, "--turn-index", "-1"],
            "INCOMPLETE: --turn-index must be >= 0",
        ),
        (
            "tools/atheris_fuzz_router.py",
            ["--issue", ISSUE_ID, "--seconds", "0"],
            "INCOMPLETE: --seconds must be > 0",
        ),
        (
            "tools/mirror_calibration_bench.py",
            ["missing-session-report.json", "--issue", ISSUE_ID, "--min-avg", "inf"],
            "INCOMPLETE: --min-avg must be a finite float",
        ),
        (
            "tools/mutation_suite.py",
            ["--issue", ISSUE_ID, "--engine", "builtin", "--target", "nope", "--dry-run"],
            "INCOMPLETE: --engine builtin supports only --target values: xyzgl",
        ),
    ],
)
def test_bug101_invalid_cli_inputs_fail_before_run_bundle(
    tmp_path: Path,
    tool_rel: str,
    args: list[str],
    expected_stdout: str,
) -> None:
    run_root = tmp_path / "runs"
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    result = _run(tool_rel, args, env=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert expected_stdout in result.stdout
    assert not run_root.exists()
