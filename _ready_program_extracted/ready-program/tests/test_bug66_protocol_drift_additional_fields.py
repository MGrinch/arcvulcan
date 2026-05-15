import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "protocol_drift_radar.py"
ISSUE = "ISSUE-20260315-066"


def _run(tmp_path: Path, name: str, doc: dict):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(path), "--issue", ISSUE, "--allow-external-path"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    match = re.search(r"wrote outputs to (.+)\s*$", proc.stdout.strip())
    run_dir = Path(match.group(1).strip()) if match else None
    report = None
    if run_dir is not None and (run_dir / "protocol_drift_report.json").exists():
        report = json.loads((run_dir / "protocol_drift_report.json").read_text(encoding="utf-8"))
    return proc, report


def test_protocol_drift_radar_scans_turn_report_additional_tutor_fields(tmp_path):
    proc, report = _run(
        tmp_path,
        "turn_report.json",
        {
            "schema_version": "turn_report@1",
            "turn_result": {
                "turn_index": 0,
                "reply": "plain reply",
                "teaching_block": "As the mirror, I will answer for the learner.",
                "evaluation": "I am simulating the learner for this turn.",
                "next_question": "As the mirror, what is the next step?",
                "config": {},
                "input": "user input",
                "backend": "Tutor",
            },
        },
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert report is not None, proc.stdout + proc.stderr
    assert any(
        f.get("role") in {"turn_teaching_block", "turn_evaluation", "turn_next_question"}
        for f in report.get("findings", [])
    ), report


def test_protocol_drift_radar_scans_session_node_title_and_eval_next_question(tmp_path):
    proc, report = _run(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s-bug66",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "node_title": "As the mirror, I will answer for the learner.",
                    "user_state": "active",
                    "teach": {
                        "teaching_block": "Teach block.",
                        "question": "What changed?",
                        "prompt_meta": {},
                    },
                    "mirror": {"answer": "I think it is fine.", "meta": {}},
                    "eval": {
                        "user_answer": "answer",
                        "mirror_answer": "I think it is fine.",
                        "evaluation": "ok",
                        "gaps": "none",
                        "next_action": "continue",
                        "next_question": "I am simulating the learner while I ask this.",
                        "prompt_meta": {},
                    },
                }
            ],
        },
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert report is not None, proc.stdout + proc.stderr
    assert any(
        f.get("role") in {"session_node_title", "eval_next_question"}
        for f in report.get("findings", [])
    ), report
