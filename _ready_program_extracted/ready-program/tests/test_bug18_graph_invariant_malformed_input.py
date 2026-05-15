import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "graph_invariant_checker.py"
ISSUE = "ISSUE-20260315-018"


def _run_dirs(runs_dir: Path) -> list[Path]:
    return sorted(p for p in runs_dir.iterdir() if p.is_dir())


def _run_tool(case_dir: Path, runs_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)}
    return subprocess.run(
        [sys.executable, str(TOOL), str(case_dir), "--issue", ISSUE],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def test_array_root_fails_but_still_writes_report(tmp_path):
    case_dir = tmp_path / "array-root"
    case_dir.mkdir()
    (case_dir / "knowledge_graph.json").write_text("[]\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    proc = _run_tool(case_dir, runs_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    run_dirs = _run_dirs(runs_dir)
    assert len(run_dirs) == 1
    report = json.loads((run_dirs[0] / "graph_invariant_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "FAIL"
    assert "knowledge_graph root must be an object" in report["problems"]
    assert (run_dirs[0] / "graph_invariant_summary.md").exists()
    assert "FAIL: wrote outputs to" in proc.stdout


def test_schema_invalid_nodes_fail_without_strict_mode(tmp_path):
    case_dir = tmp_path / "invalid-shapes"
    case_dir.mkdir()
    (case_dir / "knowledge_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "knowledge_graph@1",
                "nodes": [
                    7,
                    {
                        "node_id": "n1",
                        "title": True,
                        "summary": False,
                        "required_keywords": [123],
                        "confidence": "0.8",
                        "fragility_flags": [456],
                        "last_verified_turn": True,
                    },
                    {
                        "node_id": "n2",
                        "title": "Valid title",
                        "required_keywords": [],
                        "confidence": 0.1,
                        "fragility_flags": [],
                        "last_verified_turn": 0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs"
    proc = _run_tool(case_dir, runs_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = json.loads((_run_dirs(runs_dir)[0] / "graph_invariant_report.json").read_text(encoding="utf-8"))
    problems = report["problems"]

    assert report["overall"] == "FAIL"
    assert "node[0] must be object" in problems
    assert "node n1: title not string" in problems
    assert "node n1: summary not string" in problems
    assert "node n1: required_keywords[0] not string" in problems
    assert "node n1: fragility_flags[0] not string" in problems
    assert "node n1: confidence not a number" in problems
    assert "node n1: last_verified_turn not int" in problems
    assert "node[2] missing required fields: summary" in problems


def test_malformed_session_report_is_incomplete(tmp_path):
    case_dir = tmp_path / "malformed-session"
    case_dir.mkdir()
    (case_dir / "knowledge_graph.json").write_text(
        json.dumps(
            {
                "schema_version": "knowledge_graph@1",
                "nodes": [
                    {
                        "node_id": "n1",
                        "title": "Title",
                        "summary": "Summary",
                        "required_keywords": ["alpha"],
                        "confidence": 0.8,
                        "fragility_flags": [],
                        "last_verified_turn": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "session_report.json").write_text('{"schema_version": ', encoding="utf-8")

    runs_dir = tmp_path / "runs"
    proc = _run_tool(case_dir, runs_dir)

    assert proc.returncode == 2, proc.stdout + proc.stderr
    report = json.loads((_run_dirs(runs_dir)[0] / "graph_invariant_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "INCOMPLETE"
    assert "session_report parse failed" in report["details"]
    assert "INCOMPLETE: wrote outputs to" in proc.stdout
