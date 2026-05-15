from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import node_evolution_diff  # noqa: E402


def _write_graph(path: Path, confidence: float) -> Path:
    path.write_text(
        json.dumps({"nodes": [{"node_id": "n1", "confidence": confidence}]}),
        encoding="utf-8",
    )
    return path


def _run_diff(monkeypatch, tmp_path: Path, turn_payload: dict) -> dict:
    before = _write_graph(tmp_path / "before.json", 0.2)
    after = _write_graph(tmp_path / "after.json", 0.9)
    session_report = tmp_path / "session_report.json"
    session_report.write_text(
        json.dumps({"turns": [turn_payload]}),
        encoding="utf-8",
    )

    run_dir = tmp_path / "run"

    def fake_allocate_run_dir(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(node_evolution_diff, "allocate_run_dir", fake_allocate_run_dir)
    monkeypatch.setattr(node_evolution_diff, "_run_id", lambda: "bug130")

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            "node_evolution_diff.py",
            str(before),
            str(after),
            "--session-report",
            str(session_report),
            "--issue",
            "ISSUE-20260319-130",
        ]
        rc = node_evolution_diff.main()
    finally:
        sys.argv = old_argv

    assert rc == 0
    return json.loads((run_dir / "node_evolution_report.json").read_text(encoding="utf-8"))


def test_links_close_turn_from_canonical_eval_next_action(monkeypatch, tmp_path: Path) -> None:
    report = _run_diff(
        monkeypatch,
        tmp_path,
        {
            "turn_index": 7,
            "node_id": "n1",
            "eval": {"next_action": "CLOSE_NODE"},
        },
    )

    assert report["changed"] == [
        {
            "node_id": "n1",
            "diff": {"confidence": {"before": 0.2, "after": 0.9}},
            "linked_close_turn": 7,
        }
    ]


def test_falls_back_to_legacy_top_level_next_action(monkeypatch, tmp_path: Path) -> None:
    report = _run_diff(
        monkeypatch,
        tmp_path,
        {
            "turn_index": 3,
            "node_id": "n1",
            "next_action": "CLOSE_NODE",
            "eval": {},
        },
    )

    assert report["changed"] == [
        {
            "node_id": "n1",
            "diff": {"confidence": {"before": 0.2, "after": 0.9}},
            "linked_close_turn": 3,
        }
    ]
