import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "ontario_claims_citation_guard.py"
ISSUE = "ISSUE-20260318-122"


def _run(tmp_path: Path, name: str, doc: dict):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(path), "--issue", ISSUE, "--enforce"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    run_dir = None
    report = None
    for pattern in (r"wrote outputs to (.+)\s*$", r"\(wrote (.+)\)\s*$"):
        match = re.search(pattern, proc.stdout.strip())
        if match:
            candidate = Path(match.group(1).strip())
            if candidate.exists():
                run_dir = candidate
                break
    if run_dir is not None and (run_dir / "ontario_claims_report.json").exists():
        report = json.loads((run_dir / "ontario_claims_report.json").read_text(encoding="utf-8"))
    return proc, report


def test_ontario_claims_guard_scans_session_eval_gaps_and_questions(tmp_path):
    proc, report = _run(
        tmp_path,
        "session_report.json",
        {
            "schema_version": "session_report@1",
            "session_id": "s-bug122",
            "max_turns": 1,
            "turns": [
                {
                    "turn_index": 0,
                    "node_id": "n1",
                    "node_title": "Arc control",
                    "user_state": "active",
                    "teach": {
                        "teaching_block": "Teach block.",
                        "question": "Which Ontario W47.1 clause applies here?",
                        "prompt_meta": {},
                    },
                    "mirror": {"answer": "I am not sure.", "meta": {}},
                    "eval": {
                        "user_answer": "No idea.",
                        "mirror_answer": "No idea.",
                        "evaluation": "Looks incomplete.",
                        "gaps": "Ontario CSA W47.1 requires continuous visual inspection here.",
                        "next_action": "PROBE",
                        "next_question": "What does Ontario code require before welding?",
                        "prompt_meta": {},
                    },
                }
            ],
        },
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert report is not None, proc.stdout + proc.stderr
    locations = {f.get("location") for f in report.get("findings", [])}
    assert "turns[0].teach.question" in locations
    assert "turns[0].eval.gaps" in locations
    assert "turns[0].eval.next_question" in locations


def test_ontario_claims_guard_scans_standalone_turn_result_fields(tmp_path):
    proc, report = _run(
        tmp_path,
        "turn_report.json",
        {
            "schema_version": "turn_report@1",
            "turn_result": {
                "turn_index": 0,
                "config": {},
                "input": "learner input",
                "seed": 1337,
                "reply": "Plain reply with no Ontario claims.",
                "backend": "Tutor",
                "evaluation": "Ontario code requires a different joint prep here.",
                "next_action": "Ontario W47.1 follow-up is required.",
                "next_question": "What does Ontario CSA W47 say next?",
                "prompt_meta": {},
            },
        },
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert report is not None, proc.stdout + proc.stderr
    locations = {f.get("location") for f in report.get("findings", [])}
    assert "turn.evaluation" in locations
    assert "turn.next_action" in locations
    assert "turn.next_question" in locations
