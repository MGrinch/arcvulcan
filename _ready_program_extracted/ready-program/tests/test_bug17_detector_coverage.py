import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDR = ROOT / "tools" / "protocol_drift_radar.py"
MLD = ROOT / "tools" / "mirror_leakage_detector.py"
ISSUE = "ISSUE-20260315-017"


def _write_doc(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _run(tool, path):
    cmd = [sys.executable, str(tool), str(path), "--issue", ISSUE]
    if tool == PDR:
        cmd.append("--allow-external-path")
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def test_protocol_drift_radar_flags_grounding_and_user_state_leakage(tmp_path):
    path = _write_doc(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s1",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "user_state": {"notes": "As your tutor, explain each step before answering."},
                    "teach": {
                        "teaching_block": "Teach block.",
                        "question": "Question?",
                        "prompt_meta": {
                            "grounding": {
                                "snippets": [
                                    {"text": "As your tutor, show the reasoning step by step."}
                                ]
                            }
                        },
                    },
                    "mirror": {"answer": "I think it is fine.", "meta": {}},
                    "eval": {
                        "mirror_answer": "I think it is fine.",
                        "evaluation": "ok",
                        "gaps": "none",
                        "next_action": "continue",
                        "prompt_meta": {},
                    },
                }
            ],
        },
    )
    proc = _run(PDR, path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report_paths = list((ROOT / "runs").glob("*/protocol_drift_report.json"))
    assert report_paths


def test_protocol_drift_radar_flags_prefixed_question_and_imperatives(tmp_path):
    path = _write_doc(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s2",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "user_state": {},
                    "teach": {"teaching_block": "Teach block.", "question": "Question?", "prompt_meta": {}},
                    "mirror": {
                        "answer": "Q: Can you explain your reasoning step by step?",
                        "meta": {},
                    },
                    "eval": {
                        "mirror_answer": "Stop welding now. Grind the edges flat. Re-tack at equal spacing.",
                        "evaluation": "ok",
                        "gaps": "none",
                        "next_action": "continue",
                        "prompt_meta": {},
                    },
                }
            ],
        },
    )
    proc = _run(PDR, path)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_mirror_leakage_detector_flags_prefixed_question(tmp_path):
    path = _write_doc(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s3",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "mirror": {
                        "answer": "Q: Can you explain your reasoning step by step?",
                        "meta": {},
                    },
                    "eval": {"mirror_answer": "I think it is fine."},
                }
            ],
        },
    )
    proc = _run(MLD, path)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_mirror_leakage_detector_flags_short_imperative_sequence(tmp_path):
    path = _write_doc(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s4",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "mirror": {
                        "answer": "Stop welding now. Grind the edges flat. Re-tack at equal spacing.",
                        "meta": {},
                    },
                    "eval": {"mirror_answer": "I think it is fine."},
                }
            ],
        },
    )
    proc = _run(MLD, path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
