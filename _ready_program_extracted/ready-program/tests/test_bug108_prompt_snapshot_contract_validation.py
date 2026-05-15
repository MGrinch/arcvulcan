from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo_fixture(dst_repo: Path) -> None:
    dst_repo.mkdir()
    for rel in ["tools", "xyzgl", "curriculum", "snapshots"]:
        src = REPO_ROOT / rel
        dst = dst_repo / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            raise AssertionError(f"missing fixture source: {src}")


def _latest_run_report(repo: Path) -> dict:
    run_dir = sorted((repo / "runs").iterdir())[-1]
    return json.loads((run_dir / "prompt_snapshot_report.json").read_text(encoding="utf-8"))


def test_prompt_snapshot_guard_rejects_contract_drift_in_existing_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _copy_repo_fixture(repo)

    snap = repo / "snapshots" / "prompt_snapshots.json"
    if snap.exists():
        snap.unlink()

    init_proc = subprocess.run(
        [sys.executable, "tools/prompt_snapshot_guard.py", "--issue", "ISSUE-20260315-108", "--update"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    assert init_proc.returncode == 0, init_proc.stdout + init_proc.stderr

    baseline = json.loads(snap.read_text(encoding="utf-8"))
    baseline["schema_version"] = "prompt_snapshots@0"
    baseline["cases"].pop("protocol_only")
    baseline["cases"]["stale_extra_case"] = {
        "sha256": "0" * 64,
        "length": 0,
        "meta": {"protocol_regrounded": False, "grounding_enabled": False},
    }
    baseline["cases"]["no_protocol_no_grounding"]["length"] += 7
    baseline["cases"]["no_protocol_no_grounding"]["meta"]["protocol_regrounded"] = True
    snap.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "tools/prompt_snapshot_guard.py", "--issue", "ISSUE-20260315-108"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _latest_run_report(repo)
    assert report["overall"] == "FAIL"
    assert "baseline schema_version mismatch: expected prompt_snapshots@1, got 'prompt_snapshots@0'" in report["problems"]
    assert "missing baseline case: protocol_only" in report["problems"]
    assert "extra baseline case: stale_extra_case" in report["problems"]
    assert "case no_protocol_no_grounding: length mismatch" in report["problems"]
    assert "case no_protocol_no_grounding: meta mismatch" in report["problems"]
