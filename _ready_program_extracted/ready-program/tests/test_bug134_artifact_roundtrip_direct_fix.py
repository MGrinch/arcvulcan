from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260319-134"


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _latest_run(root: Path) -> Path:
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    assert runs, "expected a run bundle"
    return runs[-1]


def test_artifact_roundtrip_fix_accepts_supported_direct_json_file_outside_runs_root(tmp_path: Path) -> None:
    run_root = tmp_path / "tool-runs"
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    artifact_path = tmp_path / "external-artifacts" / "payload.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text('{"z": 9, "a": 1}\n', encoding="utf-8")

    result = _run(
        [sys.executable, "tools/artifact_roundtrip.py", "--issue", ISSUE_ID, "--fix", str(artifact_path)],
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    assert artifact_path.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "z": 9\n}\n'

    run_dir = _latest_run(run_root)
    report = json.loads((run_dir / "artifact_roundtrip_report.json").read_text(encoding="utf-8"))
    assert report["path"] == str(artifact_path)
    assert report["fixed"] is True
    assert report["files"] == [
        {
            "file": str(artifact_path),
            "status": "PASS",
            "changed": True,
        }
    ]
