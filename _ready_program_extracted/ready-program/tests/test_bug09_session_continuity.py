from __future__ import annotations

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.orchestrator.phases import EvalPhase, TeachPhase
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator import session_loop


def _two_node_graph() -> KnowledgeGraph:
    return KnowledgeGraph(
        nodes=[
            Node(
                node_id="a_joint_fitup",
                title="Joint fit-up",
                summary="Explain fit-up and why gap control matters before welding.",
                required_keywords=["fit", "gap"],
                confidence=0.0,
            ),
            Node(
                node_id="b_arc_length",
                title="Arc length",
                summary="Explain why arc length changes penetration and spatter.",
                required_keywords=["arc", "length"],
                confidence=0.0,
            ),
        ]
    )


def test_run_session_carries_latest_user_state_into_next_node_and_export(monkeypatch) -> None:
    teach_calls: list[dict] = []
    budget = TeachingBudget(min_sentences=1, max_sentences=1, density="light")

    def fake_teach_phase(*, node_id: str, user_state: str, **kwargs):
        teach_calls.append({"node_id": node_id, "user_state": user_state})
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block=f"Teach {node_id}",
            question=f"Question for {node_id}?",
            prompt_meta={"phase": "TEACH"},
        )

    def fake_eval_phase(*, node_id: str, user_answer: str, mirror_answer: str | None, turn_index: int, **kwargs):
        return EvalPhase(
            node_id=node_id,
            user_answer=user_answer,
            mirror_answer=mirror_answer,
            evaluation="ok",
            gaps="",
            next_action="CLOSE_NODE",
            next_question=None,
            prompt_meta={"phase": "EVAL"},
        )

    monkeypatch.setattr(session_loop, "run_teach_phase", fake_teach_phase)
    monkeypatch.setattr(session_loop, "run_mirror_prediction", lambda **kwargs: (None, None))
    monkeypatch.setattr(session_loop, "run_eval_phase", fake_eval_phase)

    answers = iter([
        ("Fit-up matters because a consistent gap keeps alignment stable before welding.", {"typing_ms": 500}),
        ("Arc length matters because it changes the puddle and penetration during welding.", {"typing_ms": 500}),
    ])
    report, _ = session_loop.run_session(
        session_id="session-bug-09-next-node",
        cfg=XYZGLConfig(),
        seed=7,
        max_turns=2,
        graph=_two_node_graph(),
        input_provider=lambda prompt: next(answers),
    )

    assert [call["user_state"] for call in teach_calls] == ["frustrated", "flow"]
    exported = report.to_json()
    second_turn = exported["turns"][1]
    assert second_turn["teach"]["user_state"] == "flow"
    assert second_turn["teach"]["prompt_meta"]["continuity"] == {
        "turn_kind": "teach",
        "state_source": "carried_forward",
        "carried_user_state": "flow",
        "source_turn_index": 0,
    }


def test_run_session_probe_turn_exports_same_continuity_runtime_used(monkeypatch) -> None:
    probe_calls: list[dict] = []
    budget = TeachingBudget(min_sentences=1, max_sentences=1, density="light")

    def fake_teach_phase(*, node_id: str, user_state: str, **kwargs):
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block="Initial teach",
            question="Initial question?",
            prompt_meta={"phase": "TEACH"},
        )

    def fake_probe_phase(*, node_id: str, user_state: str, pointed_question: str, **kwargs):
        probe_calls.append({"node_id": node_id, "user_state": user_state, "pointed_question": pointed_question})
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block="Probe hint",
            question=pointed_question,
            prompt_meta={"phase": "PROBE"},
        )

    def fake_eval_phase(*, node_id: str, user_answer: str, mirror_answer: str | None, turn_index: int, **kwargs):
        next_action = "PROBE" if turn_index == 0 else "CLOSE_NODE"
        next_question = "Why does that change the puddle?" if turn_index == 0 else None
        return EvalPhase(
            node_id=node_id,
            user_answer=user_answer,
            mirror_answer=mirror_answer,
            evaluation="ok",
            gaps="",
            next_action=next_action,
            next_question=next_question,
            prompt_meta={"phase": "EVAL"},
        )

    monkeypatch.setattr(session_loop, "run_teach_phase", fake_teach_phase)
    monkeypatch.setattr(session_loop, "run_probe_phase", fake_probe_phase)
    monkeypatch.setattr(session_loop, "run_mirror_prediction", lambda **kwargs: (None, None))
    monkeypatch.setattr(session_loop, "run_eval_phase", fake_eval_phase)

    answers = iter([
        ("I understand because travel angle changes the puddle and bead shape during welding.", {"typing_ms": 500}),
        ("It changes puddle support and bead control.", {"typing_ms": 500}),
    ])
    report, _ = session_loop.run_session(
        session_id="session-bug-09-probe",
        cfg=XYZGLConfig(),
        seed=11,
        max_turns=2,
        graph=_two_node_graph(),
        input_provider=lambda prompt: next(answers),
    )

    assert probe_calls == [{
        "node_id": "a_joint_fitup",
        "user_state": "flow",
        "pointed_question": "Why does that change the puddle?",
    }]
    exported = report.to_json()
    second_turn = exported["turns"][1]
    assert second_turn["teach"]["question"] == "Why does that change the puddle?"
    assert second_turn["teach"]["prompt_meta"]["continuity"] == {
        "turn_kind": "probe",
        "state_source": "probe_followup",
        "carried_user_state": "flow",
        "source_turn_index": 0,
        "source_question": "Why does that change the puddle?",
    }
