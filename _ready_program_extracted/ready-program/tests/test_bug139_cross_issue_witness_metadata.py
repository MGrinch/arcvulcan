import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_TOOL = ROOT / "tools" / "graph_invariant_checker.py"
MIRROR_TOOL = ROOT / "tools" / "mirror_leakage_detector.py"
CLI_ISSUE = "ISSUE-20260314-139"


def test_graph_invariant_checker_rejects_conflicting_embedded_issue_ids(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "knowledge_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "knowledge_graph@1",
                "nodes": [
                    {
                        "node_id": "n1",
                        "confidence": 0.5,
                        "last_verified_turn": 0,
                        "required_keywords": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "session_report.json").write_text(
        json.dumps(
            {
                "schema_version": "witness_event@1",
                "issue_id": CLI_ISSUE,
                "payload": {
                    "session_report": {
                        "schema_version": "session_report@1",
                        "issue_id": "ISSUE-20260314-999",
                        "turns": [{"turn_index": 0, "node_id": "n1"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(GRAPH_TOOL), str(run_dir), "--issue", CLI_ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "conflicting embedded issue_ids" in (proc.stdout + proc.stderr)


def test_mirror_leakage_detector_rejects_conflicting_embedded_issue_ids(tmp_path):
    session_path = tmp_path / "session_report.json"
    session_path.write_text(
        json.dumps(
            {
                "schema_version": "witness_event@1",
                "issue_id": CLI_ISSUE,
                "payload": {
                    "session_report": {
                        "schema_version": "session_report@1",
                        "issue_id": "ISSUE-20260314-999",
                        "turns": [
                            {
                                "turn_index": 0,
                                "node_id": "n1",
                                "mirror": {"answer": "I think this is fine."},
                                "eval": {"mirror_answer": "I think this is fine."},
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(MIRROR_TOOL), str(session_path), "--issue", CLI_ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "conflicting embedded issue_ids" in (proc.stdout + proc.stderr)
