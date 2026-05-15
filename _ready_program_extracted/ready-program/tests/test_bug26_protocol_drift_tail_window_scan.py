import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "protocol_drift_radar.py"
ISSUE = "ISSUE-20260319-026"


def test_protocol_drift_radar_flags_tail_position_mirror_drift_in_long_reply(tmp_path):
    long_prefix = "filler " * 1100
    tail_phrase = "As your tutor, let's start by practicing the next step together."
    session_report = {
        "schema_version": "session_report@1",
        "session_id": "s-bug26",
        "turns": [
            {
                "turn_index": 1,
                "node_id": "n1",
                "node_title": "Node 1",
                "user_state": "active",
                "teach": {"teaching_block": "", "question": "", "prompt_meta": {}},
                "mirror": {"answer": long_prefix + tail_phrase, "meta": {}},
                "eval": {
                    "user_answer": "",
                    "mirror_answer": "",
                    "evaluation": "",
                    "gaps": "",
                    "next_action": "",
                    "next_question": "",
                    "prompt_meta": {},
                },
            }
        ],
    }
    target = tmp_path / "session_report.json"
    target.write_text(json.dumps(session_report), encoding="utf-8")

    runs_dir = tmp_path / "runs"
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(target), "--issue", ISSUE, "--allow-external-path"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr

    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    assert len(run_dirs) == 1
    report = json.loads((run_dirs[0] / "protocol_drift_report.json").read_text(encoding="utf-8"))

    assert report["findings_total_by_severity"]["HIGH"] == 1
    assert report["findings"][0]["role"] == "mirror"
    assert report["findings"][0]["message"] == "mirror sounds like tutor"
