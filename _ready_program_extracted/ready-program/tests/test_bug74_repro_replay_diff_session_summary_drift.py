from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import repro_replay_diff as replay_diff


def test_repro_replay_diff_session_fails_when_session_summary_drifts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_report_path = tmp_path / "session_report.json"
    session_summary_path = tmp_path / "session_summary.md"
    session_report = {
        "schema_version": "session_report@1",
        "session_id": "s1",
        "seed": 11,
        "turns": [
            {
                "node_title": "Root Cause Analysis",
                "user_state": "flow",
                "teach": {
                    "user_state": "frustrated",
                    "question": "What caused the porosity?",
                },
                "eval": {
                    "user_answer": "Gas shielding broke down.",
                    "evaluation": "ok",
                    "gaps": "",
                    "next_action": "CLOSE_NODE",
                    "next_question": "",
                },
            }
        ],
    }
    session_report_path.write_text(json.dumps(session_report, indent=2), encoding="utf-8")
    session_summary_path.write_text(
        "# Session Summary\n\n"
        "## Last Turn\n\n"
        "**Node:** ```text\nRoot Cause Analysis\n```\n\n"
        "**Tutor State:** `frustrated`\n\n"
        "**Post-Eval State:** `flow`\n\n"
        "**Tutor Question:** ```text\nWhat caused the crack?\n```\n\n"
        "**User Answer:** ```text\nGas shielding broke down.\n```\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        replay_diff,
        "_replay_session",
        lambda sr, *, seed: ({"turns": sr["turns"]}, {"nodes": []}),
    )

    status, problems, diff, seed_out = replay_diff._check_session_report(session_report_path)

    assert status == ("FAIL", 1)
    assert seed_out == 11
    assert any(problem.startswith("session_summary.md: mismatch tutor_question:") for problem in problems)
    summary_diff = diff["bundle_crosscheck"]["session_summary"]
    assert summary_diff["expected"]["tutor_question"]["sha256"] != summary_diff["actual"]["tutor_question"]["sha256"]
