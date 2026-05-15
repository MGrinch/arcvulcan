import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "mirror_leakage_detector.py"
ISSUE = "ISSUE-20260315-071"


def _run(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(path), "--issue", ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return proc


def _valid_turn(*, turn_index=0, mirror_answer="I think the bracket sits here."):
    return {
        "turn_index": turn_index,
        "node_id": "n1",
        "node_title": "Node 1",
        "user_state": "active",
        "teach": {
            "teaching_block": "Teach block.",
            "question": "Question?",
            "prompt_meta": {},
        },
        "mirror": {"answer": mirror_answer, "meta": {}},
        "eval": {
            "user_answer": "A",
            "mirror_answer": mirror_answer,
            "evaluation": "ok",
            "gaps": "none",
            "next_action": "continue",
            "next_question": "Next?",
            "prompt_meta": {},
        },
    }


def test_valid_direct_session_report_still_passes(tmp_path):
    proc = _run(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s1",
            "max_turns": 1,
            "turns": [_valid_turn()],
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS:" in proc.stdout


def test_missing_required_session_root_fields_is_incomplete(tmp_path):
    proc = _run(
        tmp_path,
        "missing-root-fields.json",
        {
            "schema_version": "session_report@1",
            "turns": [_valid_turn()],
        },
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "malformed session input" in proc.stdout
    assert "session_report.session_id" in proc.stdout or "session_report.max_turns" in proc.stdout


def test_string_turn_index_is_rejected_before_scanning(tmp_path):
    turn = _valid_turn(turn_index="oops", mirror_answer="You should start by checking the weld.")
    proc = _run(
        tmp_path,
        "bad-turn-index.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s1",
            "max_turns": 1,
            "turns": [turn],
        },
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "malformed session input" in proc.stdout
    assert "turn_index" in proc.stdout
    assert "mirror role leakage" not in proc.stdout


def test_turn_index_must_fit_within_max_turns(tmp_path):
    proc = _run(
        tmp_path,
        "turn-over-budget.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s1",
            "max_turns": 1,
            "turns": [_valid_turn(turn_index=3)],
        },
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "malformed session input" in proc.stdout
    assert "turn_index" in proc.stdout
