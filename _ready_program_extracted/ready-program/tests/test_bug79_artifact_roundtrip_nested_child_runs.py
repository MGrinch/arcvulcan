from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260320-079"


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _latest_run(root: Path) -> Path:
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    assert runs, "expected a run bundle"
    return runs[-1]


def test_artifact_roundtrip_traverses_and_repairs_nested_child_runs_for_directory_targets(tmp_path: Path) -> None:
    run_root = tmp_path / "tool-runs"
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    bundle_dir = tmp_path / "external-run-bundle"
    child_dir = bundle_dir / "child_runs" / "coverage_gate_child"
    child_dir.mkdir(parents=True)

    top_level = bundle_dir / "run.json"
    nested = child_dir / "coverage_raw.json"
    top_level.write_text('{"z": 9, "a": 1}\n', encoding="utf-8")
    nested.write_text('{"outer": {"z": 3, "a": 2}, "b": 1}\n', encoding="utf-8")

    strict = _run(
        [sys.executable, "tools/artifact_roundtrip.py", "--issue", ISSUE_ID, "--strict", str(bundle_dir)],
        env=env,
    )
    assert strict.returncode == 1, strict.stdout + strict.stderr

    strict_run_dir = _latest_run(run_root)
    strict_report = json.loads((strict_run_dir / "artifact_roundtrip_report.json").read_text(encoding="utf-8"))
    strict_rows = {Path(row["file"]): row for row in strict_report["files"]}

    assert strict_report["path"] == str(bundle_dir)
    assert strict_rows[top_level]["status"] == "FAIL"
    assert strict_rows[nested]["status"] == "FAIL"
    assert strict_rows[nested]["changed"] is True

    fixed = _run(
        [sys.executable, "tools/artifact_roundtrip.py", "--issue", ISSUE_ID, "--fix", str(bundle_dir)],
        env=env,
    )
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr

    assert top_level.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "z": 9\n}\n'
    assert nested.read_text(encoding="utf-8") == '{\n  "b": 1,\n  "outer": {\n    "a": 2,\n    "z": 3\n  }\n}\n'

    fixed_run_dir = _latest_run(run_root)
    fixed_report = json.loads((fixed_run_dir / "artifact_roundtrip_report.json").read_text(encoding="utf-8"))
    fixed_rows = {Path(row["file"]): row for row in fixed_report["files"]}

    assert fixed_rows[top_level] == {"file": str(top_level), "status": "PASS", "changed": True}
    assert fixed_rows[nested] == {"file": str(nested), "status": "PASS", "changed": True}
