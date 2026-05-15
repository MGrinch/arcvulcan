import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "protocol_drift_radar.py"
ISSUE = "ISSUE-20260315-118"


def test_high_findings_are_preserved_when_warn_budget_is_saturated(tmp_path):
    warn_text = (
        "This mirror reply is highly confident and fully declarative without hedging or uncertainty. "
        "It keeps asserting conclusions in a flat, teacher-like tone while avoiding any question marks or self-doubt. "
        "The message is intentionally long so it crosses the assertiveness threshold used by the detector."
    )

    turns = []
    for idx in range(1000):
        turns.append(
            {
                "turn_index": idx,
                "node_id": f"n{idx}",
                "node_title": f"Node {idx}",
                "user_state": "active",
                "teach": {"teaching_block": "", "question": "", "prompt_meta": {}},
                "mirror": {"answer": warn_text, "meta": {}},
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
        )

    turns.append(
        {
            "turn_index": 1000,
            "node_id": "n1000",
            "node_title": "Node 1000",
            "user_state": "active",
            "teach": {
                "teaching_block": "",
                "question": "I am the mirror and I will guide this lesson now.",
                "prompt_meta": {},
            },
            "mirror": {"answer": "", "meta": {}},
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
    )

    session_report = {
        "schema_version": "session_report@1",
        "session_id": "s-bug118",
        "max_turns": len(turns),
        "turns": turns,
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

    assert report["findings_total"] == 1001
    assert report["findings_truncated"] == 1
    assert report["findings_total_by_severity"]["HIGH"] == 1
    assert report["findings_total_by_severity"]["WARN"] == 1000
    assert report["findings_kept_by_severity"]["HIGH"] == 1
    assert report["findings_kept_by_severity"]["WARN"] == 999
    assert len(report["findings"]) == 1000
    assert report["findings"][0]["severity"] == "HIGH"
    assert report["findings"][0]["role"] == "tutor_question"
