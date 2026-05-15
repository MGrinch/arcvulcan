from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import atheris_fuzz_router as tool

ISSUE = "ISSUE-20260319-125"


def test_missing_atheris_reports_incomplete_not_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(sys, "argv", ["atheris_fuzz_router", "--issue", ISSUE, "--seed", "7", "--seconds", "1"])

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "atheris":
            raise ModuleNotFoundError("No module named 'atheris'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    exit_code = tool.main()

    assert exit_code == 2
    out = capsys.readouterr().out
    assert "INCOMPLETE: wrote outputs to" in out

    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    assert len(run_dirs) == 1

    report = json.loads((run_dirs[0] / "atheris_fuzz_report.json").read_text(encoding="utf-8"))
    summary = (run_dirs[0] / "atheris_fuzz_summary.md").read_text(encoding="utf-8")
    run_manifest = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))

    assert report["engine"] == "fallback"
    assert report["status"] == "INCOMPLETE"
    assert report["pass"] is False
    assert "atheris unavailable" in report["notes"]
    assert "ModuleNotFoundError" in report["notes"]
    assert "- overall: **INCOMPLETE**" in summary
    assert run_manifest["exit_codes"]["2"] == "INCOMPLETE"
