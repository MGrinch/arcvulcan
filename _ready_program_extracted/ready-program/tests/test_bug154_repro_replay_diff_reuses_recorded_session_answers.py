from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HARNESS_SESSION_PATH = REPO_ROOT / "tools" / "harness_session.py"
REPRO_REPLAY_DIFF_PATH = REPO_ROOT / "tools" / "repro_replay_diff.py"
_RUN_DIR_RE = re.compile(r"wrote outputs to (?P<path>.+)$")


def _extract_run_dir(stdout: str) -> Path:
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    assert lines, "expected tool stdout to contain a run directory"
    match = _RUN_DIR_RE.search(lines[-1])
    assert match, f"expected final stdout line to contain run dir, got: {lines[-1]!r}"
    return Path(match.group("path")).resolve()


def _latest_report(runs_dir: Path, name: str) -> dict:
    report_paths = sorted(runs_dir.glob(f"*/{name}"))
    assert report_paths, f"expected at least one {name} output"
    return json.loads(report_paths[-1].read_text(encoding="utf-8"))


def test_repro_replay_diff_reuses_recorded_session_answers(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}

    harness = subprocess.run(
        [
            sys.executable,
            str(HARNESS_SESSION_PATH),
            "--issue",
            "ISSUE-20260315-154",
            "--seed",
            "1",
            "--max-turns",
            "2",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert harness.returncode == 0, harness.stdout + harness.stderr
    session_run_dir = _extract_run_dir(harness.stdout)
    assert (session_run_dir / "session_report.json").exists(), "expected harness_session to emit session_report.json"

    replay = subprocess.run(
        [
            sys.executable,
            str(REPRO_REPLAY_DIFF_PATH),
            "--issue",
            "ISSUE-20260315-154",
            "--allow-external-path",
            str(session_run_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr

    report = _latest_report(runs_dir, "replay_diff_report.json")
    assert report["overall"] == "PASS"
    assert report["problems"] == []
    assert report["diff"]["expected_hash"] == report["diff"]["replayed_hash"]
    bundle_crosscheck = report["diff"]["bundle_crosscheck"]
    assert bundle_crosscheck["knowledge_graph_expected"]["sha256"] == bundle_crosscheck["knowledge_graph_replayed"]["sha256"]
