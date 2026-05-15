from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.knowledge.heuristics import select_next_node
from xyzgl.orchestrator.session_loop import run_session


def _tied_graph() -> KnowledgeGraph:
    return KnowledgeGraph(
        nodes=[
            Node(node_id="a", title="A", summary="Explain A", required_keywords=["a"], confidence=0.0),
            Node(node_id="b", title="B", summary="Explain B", required_keywords=["b"], confidence=0.0),
            Node(node_id="c", title="C", summary="Explain C", required_keywords=["c"], confidence=0.0),
        ]
    )


def test_select_next_node_uses_seed_for_tied_candidates() -> None:
    graph = _tied_graph()

    first_seed_0 = select_next_node(graph, seed=0)
    repeat_seed_0 = select_next_node(graph, seed=0)
    first_seed_1 = select_next_node(graph, seed=1)

    assert first_seed_0.node_id == repeat_seed_0.node_id
    assert first_seed_0.node_id != first_seed_1.node_id


def test_select_next_node_avoids_immediate_repeat_inside_tie_group() -> None:
    graph = _tied_graph()

    first = select_next_node(graph, seed=1)
    second = select_next_node(graph, seed=1, avoid_node_id=first.node_id)

    assert second.node_id != first.node_id


def _session_order(seed: int) -> list[str]:
    graph = _tied_graph()

    def input_provider(prompt: str):
        node_id = "a"
        if "NODE_ID: b" in prompt:
            node_id = "b"
        elif "NODE_ID: c" in prompt:
            node_id = "c"
        return node_id, {"typing_ms": 1000}

    report, _ = run_session(
        session_id=f"bug08-{seed}",
        cfg=XYZGLConfig(),
        seed=seed,
        max_turns=3,
        graph=graph,
        input_provider=input_provider,
    )
    return [turn.node_id for turn in report.turns]


def test_run_session_preserves_seeded_tie_ordering() -> None:
    assert _session_order(0) == _session_order(0)
    assert _session_order(0) != _session_order(1)
