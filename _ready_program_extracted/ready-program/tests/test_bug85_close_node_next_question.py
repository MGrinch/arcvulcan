from __future__ import annotations

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.session_loop import run_session
from xyzgl.orchestrator import session_loop
from xyzgl.orchestrator.turn import EvalPhase, TeachPhase


def test_close_node_turn_carries_no_follow_up_question(monkeypatch):
    def fake_teach_phase(**kwargs):
        return TeachPhase(
            node_id=kwargs["node_id"],
            user_state="flow",
            budget=TeachingBudget(min_sentences=1, max_sentences=1, density="light"),
            teaching_block="Teach block.",
            question="Q1: Explain the node.",
            prompt_meta={"phase": "TEACH"},
        )

    def fake_eval_phase(**kwargs):
        return EvalPhase(
            node_id=kwargs["node_id"],
            user_answer=kwargs["user_answer"],
            mirror_answer=None,
            evaluation="Closed.",
            gaps="",
            next_action="CLOSE_NODE",
            next_question="Q2: What's the missing step in your reasoning?",
            prompt_meta={"phase": "EVAL"},
        )

    monkeypatch.setattr(session_loop, "run_teach_phase", fake_teach_phase)
    monkeypatch.setattr(session_loop, "run_eval_phase", fake_eval_phase)

    report, _ = run_session(
        session_id="session-bug-85",
        cfg=XYZGLConfig(),
        seed=1337,
        max_turns=1,
        graph=default_graph(),
        input_provider=lambda prompt: ("A complete answer.", {"typing_ms": 5000}),
    )

    assert len(report.turns) == 1
    turn = report.turns[0]
    assert turn.eval.next_action == "CLOSE_NODE"
    assert turn.eval.next_question is None

    exported = report.to_json()
    assert exported["turns"][0]["eval"]["next_action"] == "CLOSE_NODE"
    assert exported["turns"][0]["eval"]["next_question"] is None
