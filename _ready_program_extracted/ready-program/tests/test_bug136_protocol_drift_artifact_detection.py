import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "protocol_drift_radar.py"
ISSUE = "ISSUE-20260314-136"


def _run(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(path), "--issue", ISSUE, "--allow-external-path"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return proc


def test_renamed_root_turn_report_is_detected(tmp_path):
    proc = _run(
        tmp_path,
        "renamed-artifact.json",
        {
            "schema_version": "turn_report@1",
            "turn_result": {
                "turn_index": 0,
                "config": {},
                "input": "hello",
                "seed": None,
                "reply": "plain tutor reply",
                "backend": "Tutor",
            },
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no recognizable artifacts found" not in (proc.stdout + proc.stderr)



def test_renamed_root_session_report_is_detected(tmp_path):
    proc = _run(
        tmp_path,
        "staged-copy.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s1",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "node_title": "Node 1",
                    "user_state": "active",
                    "teach": {
                        "teaching_block": "Teach block.",
                        "question": "Question?",
                        "prompt_meta": {},
                    },
                    "mirror": {"answer": "I think it is fine.", "meta": {}},
                    "eval": {
                        "user_answer": "A",
                        "mirror_answer": "I think it is fine.",
                        "evaluation": "ok",
                        "gaps": "none",
                        "next_action": "continue",
                        "next_question": "Next?",
                        "prompt_meta": {},
                    },
                }
            ],
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no recognizable artifacts found" not in (proc.stdout + proc.stderr)
