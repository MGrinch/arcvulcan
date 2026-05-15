from __future__ import annotations

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.orchestrator.policies import required_keywords_audit, required_keywords_satisfied
from xyzgl.orchestrator.session_loop import run_session


def _bug121_graph() -> KnowledgeGraph:
    return KnowledgeGraph(
        nodes=[
            Node(
                node_id="pos_1f_vs_2f",
                title="Fillet positions: 1F vs 2F",
                summary=(
                    "Explain what 1F and 2F mean, how gravity affects the puddle, "
                    "and why angle and pause control change."
                ),
                required_keywords=["1f", "2f", "gravity"],
                confidence=0.0,
            )
        ]
    )


def test_required_keywords_audit_rejects_keyword_stuffed_nonsense() -> None:
    audit = required_keywords_audit(
        ["1f", "2f", "gravity"],
        "I think 1f 2f gravity you need that.",
    )

    assert audit["matched_keywords"] == ["1f", "2f", "gravity"]
    assert audit["quality_passed"] is False
    assert "insufficient_explanatory_content" in audit["quality_reasons"]
    assert audit["satisfied"] is False
    assert required_keywords_satisfied(["1f", "2f", "gravity"], "I think 1f 2f gravity you need that.") is False


def test_run_session_keeps_node_open_for_keyword_stuffed_nonsense() -> None:
    report, updated_graph = run_session(
        session_id="session-bug-121-nonsense",
        cfg=XYZGLConfig(),
        seed=1337,
        max_turns=1,
        graph=_bug121_graph(),
        input_provider=lambda prompt: ("I think 1f 2f gravity you need that.", {"typing_ms": 4000}),
    )

    assert len(report.turns) == 1
    turn = report.turns[0]
    assert turn.eval.next_action == "PROBE"
    assert turn.close_gate is not None
    assert turn.close_gate["quality_passed"] is False
    assert updated_graph.get("pos_1f_vs_2f").last_verified_turn == -1


def test_run_session_still_closes_for_coherent_keyword_complete_answer() -> None:
    answer = (
        "1F is the flat fillet position, 2F is horizontal, and gravity pulls the puddle down in 2F "
        "so you need tighter angle and pause control."
    )
    report, updated_graph = run_session(
        session_id="session-bug-121-coherent",
        cfg=XYZGLConfig(),
        seed=1337,
        max_turns=1,
        graph=_bug121_graph(),
        input_provider=lambda prompt: (answer, {"typing_ms": 5000}),
    )

    assert len(report.turns) == 1
    turn = report.turns[0]
    assert turn.eval.next_action == "CLOSE_NODE"
    assert turn.close_gate is not None
    assert turn.close_gate["quality_passed"] is True
    assert updated_graph.get("pos_1f_vs_2f").last_verified_turn == 0
