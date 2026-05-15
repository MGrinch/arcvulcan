from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260315-081"


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _make_session(tmp_path: Path, *, enable_mirror: bool) -> Path:
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path)
    cmd = [
        sys.executable,
        "tools/harness_session.py",
        "--issue",
        ISSUE_ID,
        "--seed",
        "1",
        "--max-turns",
        "2",
    ]
    if enable_mirror:
        cmd.append("--enable-mirror")
    result = _run(cmd, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    sessions = sorted(p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("session-"))
    assert sessions, "expected harness_session to create a session bundle"
    return sessions[-1]


def _latest_non_session_run(tmp_path: Path) -> Path:
    runs = sorted(
        (p for p in tmp_path.iterdir() if p.is_dir() and not p.name.startswith("session-")),
        key=lambda p: p.stat().st_mtime_ns,
    )
    assert runs, "expected tool to create a run bundle"
    return runs[-1]


@pytest.mark.parametrize(
    ("tool_rel", "tool_args", "enable_mirror"),
    [
        ("tools/reground_cadence_verifier.py", ["--every", "5"], False),
        ("tools/mirror_leakage_detector.py", [], True),
    ],
)
def test_bug81_remaining_tools_emit_canonical_run_json(tmp_path: Path, tool_rel: str, tool_args: list[str], enable_mirror: bool) -> None:
    run_root = tmp_path / "runs"
    run_root.mkdir()
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    session_dir = _make_session(run_root, enable_mirror=enable_mirror)

    tool_cmd = [sys.executable, tool_rel, "--issue", ISSUE_ID, *tool_args, str(session_dir)]
    tool_result = _run(tool_cmd, env=env)
    assert tool_result.returncode in {0, 1, 2}, tool_result.stdout + tool_result.stderr

    tool_run_dir = _latest_non_session_run(run_root)
    strict_result = _run(
        [sys.executable, "tools/artifact_roundtrip.py", "--issue", ISSUE_ID, "--strict", str(tool_run_dir)],
        env=env,
    )
    assert strict_result.returncode == 0, strict_result.stdout + strict_result.stderr
