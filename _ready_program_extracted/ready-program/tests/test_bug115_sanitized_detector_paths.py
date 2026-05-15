import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_TOOL = ROOT / "tools" / "graph_invariant_checker.py"
MIRROR_TOOL = ROOT / "tools" / "mirror_leakage_detector.py"
ISSUE = "ISSUE-20260315-115"


def _run_dirs(runs_dir: Path) -> list[Path]:
    return sorted(p for p in runs_dir.iterdir() if p.is_dir())


def test_graph_checker_uses_logical_paths_in_stdout_and_artifacts(tmp_path):
    case_dir = tmp_path / "external-graph-run"
    case_dir.mkdir()
    (case_dir / "knowledge_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "knowledge_graph@1",
                "nodes": [
                    {
                        "node_id": "n1",
                        "title": "Node title",
                        "summary": "Node summary",
                        "confidence": 0.8,
                        "last_verified_turn": 0,
                        "required_keywords": ["alpha"],
                        "fragility_flags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "session_report.json").write_text(
        json.dumps(
            {
                "schema_version": "session_report@1",
                "issue_id": ISSUE,
                "turns": [{"turn_index": 0, "node_id": "n1"}],
            }
        ),
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs-out"
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}
    proc = subprocess.run(
        [sys.executable, str(GRAPH_TOOL), str(case_dir), "--issue", ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    stdout = proc.stdout.strip()
    assert str(tmp_path) not in stdout
    assert "wrote outputs to" in stdout

    run_dirs = _run_dirs(runs_dir)
    assert len(run_dirs) == 1
    report = json.loads((run_dirs[0] / "graph_invariant_report.json").read_text(encoding="utf-8"))
    summary = (run_dirs[0] / "graph_invariant_summary.md").read_text(encoding="utf-8")

    assert report["source"] == case_dir.name
    assert str(tmp_path) not in json.dumps(report)
    assert str(tmp_path) not in summary
    assert f"- source: {case_dir.name}" in summary


def test_mirror_detector_uses_logical_paths_in_stdout_and_artifacts(tmp_path):
    session_path = tmp_path / "external-session-report.json"
    session_path.write_text(
        json.dumps(
            {
                "schema_version": "session_report@1",
                "issue_id": ISSUE,
                "turns": [
                    {
                        "turn_index": 0,
                        "node_id": "n1",
                        "mirror": {"answer": "I think I should check the fit-up first."},
                        "eval": {"mirror_answer": ""},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs-out"
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}
    proc = subprocess.run(
        [sys.executable, str(MIRROR_TOOL), str(session_path), "--issue", ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    stdout = proc.stdout.strip()
    assert str(tmp_path) not in stdout

    run_dirs = _run_dirs(runs_dir)
    assert len(run_dirs) == 1
    report = json.loads((run_dirs[0] / "mirror_leakage_report.json").read_text(encoding="utf-8"))
    summary = (run_dirs[0] / "mirror_leakage_summary.md").read_text(encoding="utf-8")

    assert report["path"] == session_path.name
    assert str(tmp_path) not in json.dumps(report)
    assert str(tmp_path) not in summary
    assert f"- path: {session_path.name}" in summary
