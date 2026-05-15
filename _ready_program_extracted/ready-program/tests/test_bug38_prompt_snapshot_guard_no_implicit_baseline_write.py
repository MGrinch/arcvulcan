from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo_fixture(dst_repo: Path, *, include_snapshots: bool = True) -> None:
    dst_repo.mkdir()
    rels = ["tools", "xyzgl", "curriculum"]
    if include_snapshots:
        rels.append("snapshots")
    for rel in rels:
        src = REPO_ROOT / rel
        dst = dst_repo / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            raise AssertionError(f"missing fixture source: {src}")


def _latest_run_report(repo: Path) -> dict:
    run_dir = sorted((repo / "runs").iterdir())[-1]
    return json.loads((run_dir / "prompt_snapshot_report.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_prompt_snapshot_guard_does_not_create_missing_baseline_without_update(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _copy_repo_fixture(repo, include_snapshots=False)

    proc = subprocess.run(
        [sys.executable, "tools/prompt_snapshot_guard.py", "--issue", "ISSUE-20260319-038"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not (repo / "snapshots").exists()
    report = _latest_run_report(repo)
    assert report["overall"] == "FAIL"
    assert report["updated_baseline"] is False
    assert report["problems"] == [
        "snapshot baseline missing; re-run with --update to create it intentionally"
    ]


def test_prompt_snapshot_guard_does_not_rewrite_stale_baseline_without_update(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _copy_repo_fixture(repo)

    snap = repo / "snapshots" / "prompt_snapshots.json"
    baseline = json.loads(snap.read_text(encoding="utf-8"))
    baseline["cases"]["protocol_only"]["length"] += 17
    snap.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    before = _sha256(snap)

    proc = subprocess.run(
        [sys.executable, "tools/prompt_snapshot_guard.py", "--issue", "ISSUE-20260319-038"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    after = _sha256(snap)
    assert after == before
    report = _latest_run_report(repo)
    assert report["overall"] == "FAIL"
    assert report["updated_baseline"] is False
    assert "case protocol_only: length mismatch" in report["problems"]
