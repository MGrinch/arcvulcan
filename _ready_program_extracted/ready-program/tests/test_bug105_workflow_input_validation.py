from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DOC_LINK_CHECKER = REPO_ROOT / "tools" / "doc_code_link_checker.py"
OVERLAY_APPLY = REPO_ROOT / "tools" / "apply_signal_fidelity_overlay.py"
SIGNAL_PORT = REPO_ROOT / "tools" / "signal_fidelity_port.py"
AI_INDEX_PATH = REPO_ROOT / "docs" / "AI_INDEX.json"


def _latest_json(runs_dir: Path, name: str) -> dict:
    matches = sorted(runs_dir.glob(f"*/{name}"))
    assert matches, f"missing {name} in {runs_dir}"
    return json.loads(matches[-1].read_text(encoding="utf-8"))


def test_doc_code_link_checker_rejects_malformed_surface_entries(tmp_path: Path) -> None:
    original = AI_INDEX_PATH.read_text(encoding="utf-8")
    runs_dir = tmp_path / "runs"
    try:
        AI_INDEX_PATH.write_text(
            json.dumps(
                {
                    "surfaces": [
                        {"path": "xyzgl/router.py"},
                        "not-an-object",
                        {"path": "tools"},
                        {"path": "README.md"},
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(DOC_LINK_CHECKER), "--issue", "ISSUE-20260314-105"],
            cwd=REPO_ROOT,
            env={**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        report = _latest_json(runs_dir, "doc_link_report.json")
        assert report["overall"] == "FAIL"
        assert "AI_INDEX surface #2 must be an object" in report["problems"]
        assert "AI_INDEX path invalid: tools" in report["problems"]
        assert "AI_INDEX path invalid: README.md" in report["problems"]
    finally:
        AI_INDEX_PATH.write_text(original, encoding="utf-8")


def test_apply_signal_fidelity_overlay_rejects_empty_overlay_directory(tmp_path: Path) -> None:
    empty_overlay = tmp_path / "empty_overlay"
    empty_overlay.mkdir()
    runs_dir = tmp_path / "runs"
    proc = subprocess.run(
        [
            sys.executable,
            str(OVERLAY_APPLY),
            "--issue",
            "ISSUE-20260314-105",
            "--overlay",
            str(empty_overlay),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _latest_json(runs_dir, "signal_fidelity_apply_report.json")
    assert report["overall"] == "FAIL"
    assert report["copied_files"] == 0
    assert "overlay application was a no-op (copied zero files)" in report["notes"]


def test_signal_fidelity_port_rejects_duplicate_key_plan_json(tmp_path: Path) -> None:
    plan_path = tmp_path / "dup_plan.json"
    plan_path.write_text(
        '{"actions": [{"src": "README.md", "to": "tools"}], "actions": []}\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(SIGNAL_PORT), "--plan", str(plan_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Invalid plan JSON: duplicate key: 'actions'" in (proc.stdout + proc.stderr)


def test_signal_fidelity_port_rejects_plan_action_missing_to(tmp_path: Path) -> None:
    plan_path = tmp_path / "missing_to.json"
    plan_path.write_text(json.dumps({"actions": [{"src": "README.md"}]}) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SIGNAL_PORT), "--plan", str(plan_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "Invalid plan action #1: missing non-empty string 'to'" in combined
    assert "KeyError" not in combined


def test_signal_fidelity_port_rejects_empty_actions_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "empty_actions.json"
    plan_path.write_text(json.dumps({"actions": []}) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SIGNAL_PORT), "--plan", str(plan_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Invalid plan: 'actions' must contain at least one action" in (proc.stdout + proc.stderr)
