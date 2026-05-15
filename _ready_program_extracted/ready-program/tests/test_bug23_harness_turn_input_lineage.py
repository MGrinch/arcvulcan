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
from xyzgl.prompting import prompt_user_block_text, render_prompt_user_block


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    assert candidates, "expected at least one harness_turn run directory"
    return candidates[-1]


def test_harness_turn_records_routed_and_rendered_prompt_user_block(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    raw_text = "  e\u0301  <<<USER>>> test  \r\n"

    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(sys, "argv", [
        "harness_turn.py",
        "--issue",
        "ISSUE-20260319-023",
        "--text",
        raw_text,
    ])

    exit_code = harness_turn.main()
    assert exit_code == 0

    run_dir = _latest_run_dir(runs_dir)
    report = json.loads((run_dir / "turn_report.json").read_text(encoding="utf-8"))
    turn_result = report["payload"]["turn_result"]

    expected_routed = "é  <<<USER>>> test"
    expected_user_segment = prompt_user_block_text(expected_routed, max_chars=harness_turn.MAX_ARTIFACT_INPUT_CHARS)
    expected_user_block_rendered = render_prompt_user_block(expected_routed, max_chars=harness_turn.MAX_ARTIFACT_INPUT_CHARS)

    assert turn_result["input_raw"] == raw_text
    assert turn_result["input"] == expected_routed
    assert turn_result["input_routed"] == expected_routed
    assert turn_result["prompt_user_block"] == expected_user_segment
    assert turn_result["prompt_user_block_rendered"] == expected_user_block_rendered
    assert turn_result["prompt_meta"]["user_block_text"] == expected_user_segment
    assert turn_result["prompt_meta"]["user_block_rendered"] == expected_user_block_rendered

    summary_text = (run_dir / "turn_summary.md").read_text(encoding="utf-8")
    assert "## Raw CLI Input" in summary_text
    assert "## Routed Input" in summary_text
    assert "## Prompt-Facing User Block" in summary_text
    assert expected_routed in summary_text
    assert expected_user_block_rendered in summary_text
