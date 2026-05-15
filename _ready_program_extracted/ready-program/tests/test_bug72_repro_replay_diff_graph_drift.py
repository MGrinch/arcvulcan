from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import repro_replay_diff as replay_diff


def test_repro_replay_diff_session_fails_when_knowledge_graph_drift_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_report_path = tmp_path / "session_report.json"
    knowledge_graph_path = tmp_path / "knowledge_graph.json"
    session_report = {
        "schema_version": "session_report@1",
        "session_id": "s1",
        "seed": 11,
        "turns": [{"turn_index": 0, "reply": "steady"}],
    }
    session_report_path.write_text(json.dumps(session_report, indent=2), encoding="utf-8")
    knowledge_graph_path.write_text(json.dumps({"nodes": [{"id": "stored"}]}, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        replay_diff,
        "_replay_session",
        lambda sr, *, seed: ({"turns": sr["turns"]}, {"nodes": [{"id": "replayed"}]}),
    )

    status, problems, diff, seed_out = replay_diff._check_session_report(session_report_path)

    assert status == ("FAIL", 1)
    assert seed_out == 11
    assert any(problem.startswith("knowledge_graph.json: mismatch:") for problem in problems)
    crosscheck = diff["bundle_crosscheck"]
    assert crosscheck["knowledge_graph_expected"]["sha256"] != crosscheck["knowledge_graph_replayed"]["sha256"]
