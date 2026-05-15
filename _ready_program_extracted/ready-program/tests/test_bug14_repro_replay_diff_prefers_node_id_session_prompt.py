from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import repro_replay_diff as replay_diff


class _FakeNode:
    def __init__(self, node_id: str, title: str, required_keywords: list[str]) -> None:
        self.node_id = node_id
        self.title = title
        self.required_keywords = required_keywords


class _FakeGraph:
    def __init__(self) -> None:
        self.nodes = [
            _FakeNode("actual-node", "Correct title", ["arc length"]),
            _FakeNode("wrong-node", "Conflicting title", ["wrong keyword"]),
        ]

    def get(self, node_id: str):
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None


def test_repro_replay_diff_session_replay_prefers_node_id_over_conflicting_title(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(replay_diff, "default_graph", lambda: _FakeGraph())

    def fake_sim_user_answer(node_id: str, required: list[str], *, seed: int) -> str:
        captured["node_id"] = node_id
        captured["required"] = list(required)
        captured["seed"] = seed
        return "simulated answer"

    monkeypatch.setattr(replay_diff, "_sim_user_answer", fake_sim_user_answer)

    def fake_run_session(*, session_id: str, cfg, seed: int, max_turns: int, graph, input_provider):
        answer, meta = input_provider(
            "NODE_ID: actual-node\n"
            "NODE: Conflicting title\n"
            "QUESTION: How do I keep arc length steady?"
        )
        captured["answer"] = answer
        captured["typing_ms"] = meta.get("typing_ms")
        return _SessionReportStub(), graph

    monkeypatch.setattr(replay_diff, "run_session", fake_run_session)

    session_report, knowledge_graph = replay_diff._replay_session(
        {"session_id": "replay-bug14", "max_turns": 1, "turns": []},
        seed=41,
    )

    assert captured["node_id"] == "actual-node"
    assert captured["required"] == ["arc length"]
    assert captured["seed"] == 41
    assert captured["answer"] == "simulated answer"
    assert captured["typing_ms"] == 4500
    assert session_report == {"schema_version": "session_report@1", "turns": []}
    assert knowledge_graph["nodes"][0]["node_id"] == "actual-node"


class _SessionReportStub:
    def to_json(self) -> dict:
        return {"schema_version": "session_report@1", "turns": []}
