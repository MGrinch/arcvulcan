from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import harness_turn


def test_turn_summary_preserves_markup_strips_controls_and_caps_size(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    args = argparse.Namespace(issue="ISSUE-20260318-024", seed=1337, text="cli")

    huge = "<keep>&\x00```tail```" + ("A" * (harness_turn.MAX_TURN_SUMMARY_CHARS * 2)) + "\x07"
    artifact_result = {
        "input_raw": huge,
        "input_routed": huge,
        "prompt_user_block": huge,
        "reply": huge,
        "mirror_prediction": huge,
        "mirror_meta": {"payload": huge},
        "backend_error": huge,
    }

    harness_turn._write_turn_outputs(
        run_dir=run_dir,
        args=args,
        run_id="RUN-024",
        overall="FAIL",
        artifact_result=artifact_result,
    )

    summary = (run_dir / "turn_summary.md").read_text(encoding="utf-8")

    assert "<keep>&" in summary
    assert "&lt;keep&gt;" not in summary
    assert "\x00" not in summary
    assert "\x07" not in summary
    assert len(summary) <= harness_turn.MAX_TURN_SUMMARY_CHARS
    assert "...<truncated>" in summary
    assert summary.count("```") >= 2
    assert summary.count("``\\`") >= 1
