from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def _run_dir_from_stdout(stdout: str) -> Path:
    return Path(stdout.strip().split()[-1])


def test_doc_code_link_checker_rejects_malformed_ai_index_entries(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ai_index = repo_root / "docs" / "AI_INDEX.json"
    backup = ai_index.read_text(encoding="utf-8") if ai_index.exists() else None
    runs_dir = tmp_path / "runs"
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}

    try:
        ai_index.parent.mkdir(parents=True, exist_ok=True)
        ai_index.write_text(
            json.dumps({"surfaces": ["oops", {"path": "tools/doc_code_link_checker.py"}]}, indent=2),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "doc_code_link_checker.py"),
                "--issue",
                "ISSUE-20260315-105",
                "--enforce",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1, result.stderr or result.stdout
        report = json.loads((_run_dir_from_stdout(result.stdout) / "doc_link_report.json").read_text(encoding="utf-8"))
        assert report["overall"] == "FAIL"
        assert "AI_INDEX surface[0] must be an object" in report["problems"]
    finally:
        if backup is None:
            ai_index.unlink(missing_ok=True)
        else:
            ai_index.write_text(backup, encoding="utf-8")


def test_apply_signal_fidelity_overlay_fails_on_empty_zip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    empty_zip = tmp_path / "empty_overlay.zip"
    with zipfile.ZipFile(empty_zip, "w"):
        pass

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "apply_signal_fidelity_overlay.py"),
            "--issue",
            "ISSUE-20260315-105",
            "--overlay",
            str(empty_zip),
        ],
        cwd=repo_root,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(tmp_path / "runs")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr or result.stdout
    report = json.loads((_run_dir_from_stdout(result.stdout) / "signal_fidelity_apply_report.json").read_text(encoding="utf-8"))
    assert report["overall"] == "FAIL"
    assert report["source_file_count"] == 0
    assert any("no regular files" in note for note in report["notes"])


def test_signal_fidelity_port_handles_bad_and_noop_plans_without_tracebacks(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    bad_plan = tmp_path / "bad_plan.json"
    bad_plan.write_text("{bad json", encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "signal_fidelity_port.py"), "--plan", str(bad_plan)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 2
    assert "INCOMPLETE: Malformed plan JSON:" in bad.stderr
    assert "Traceback" not in (bad.stdout + bad.stderr)

    noop_plan = tmp_path / "noop_plan.json"
    noop_plan.write_text(json.dumps({"actions": []}), encoding="utf-8")
    noop = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "signal_fidelity_port.py"), "--plan", str(noop_plan)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert noop.returncode == 2
    assert "non-empty actions list" in noop.stderr
    assert "Traceback" not in (noop.stdout + noop.stderr)


def test_signal_fidelity_port_valid_plan_still_copies(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    listed = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "signal_fidelity_port.py"), "--list"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    files = [line for line in listed.stdout.splitlines() if line.strip()]
    assert files

    dst_rel = "tools/_tmp_signal_fidelity_port"
    dst_dir = repo_root / dst_rel
    shutil.rmtree(dst_dir, ignore_errors=True)

    plan = tmp_path / "good_plan.json"
    plan.write_text(json.dumps({"actions": [{"src": files[0], "to": dst_rel}]}), encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "signal_fidelity_port.py"), "--plan", str(plan)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["applied"][0]["src"] == files[0]
    finally:
        shutil.rmtree(dst_dir, ignore_errors=True)
