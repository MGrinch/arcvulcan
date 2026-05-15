from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from tools import harness_turn


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    assert candidates, "expected at least one harness_turn run directory"
    return candidates[-1]


def test_harness_turn_route_failure_with_lone_surrogate_still_writes_failure_bundle(
    monkeypatch, tmp_path: Path
) -> None:
    runs_dir = tmp_path / "runs"
    bad_text = "bad\ud800input"

    def _boom(*args, **kwargs):
        raise RuntimeError("route exploded \ud800")

    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(harness_turn, "route_turn", _boom)
    monkeypatch.setattr(sys, "argv", [
        "harness_turn.py",
        "--issue",
        "ISSUE-20260318-010",
        "--text",
        bad_text,
    ])

    exit_code = harness_turn.main()
    assert exit_code == 1

    run_dir = _latest_run_dir(runs_dir)
    assert (run_dir / "turn_report.json").is_file()
    assert (run_dir / "turn_summary.md").is_file()
    assert (run_dir / "run.json").is_file()

    report = json.loads((run_dir / "turn_report.json").read_text(encoding="utf-8"))
    turn_result = report["payload"]["turn_result"]
    assert turn_result["backend_error"] == "RuntimeError: route exploded ?"
    assert turn_result["exception_message"] == "route exploded ?"
    assert turn_result["input"] == "bad?input"
    assert turn_result["input_raw"] == "bad?input"
    assert turn_result["input_routed"] == "bad?input"
    assert turn_result["prompt_user_block"] == "bad?input"

    summary_text = (run_dir / "turn_summary.md").read_text(encoding="utf-8")
    assert "RuntimeError: route exploded ?" in summary_text
    assert "bad?input" in summary_text
    assert "\ud800" not in summary_text
