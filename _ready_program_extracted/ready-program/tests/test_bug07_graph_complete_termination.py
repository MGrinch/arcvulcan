from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.orchestrator import session_loop
from xyzgl.orchestrator.phases import EvalPhase, TeachPhase
from xyzgl.orchestrator.policies import TeachingBudget


def _single_node_graph(*, confidence: float) -> KnowledgeGraph:
    return KnowledgeGraph(
        nodes=[
            Node(
                node_id="joint_fitup",
                title="Joint fit-up",
                summary="Explain fit-up and why gap control matters before welding.",
                required_keywords=["fit", "gap"],
                confidence=confidence,
            )
        ]
    )


def test_run_session_stops_when_graph_reaches_full_mastery(monkeypatch) -> None:
    budget = TeachingBudget(min_sentences=1, max_sentences=1, density="light")

    def fake_teach_phase(*, node_id: str, user_state: str, **kwargs):
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block="Short lesson.",
            question="What matters in fit-up?",
            prompt_meta={"turn_kind": "teach"},
        )

    def fake_mirror_prediction(**kwargs):
        return "mirror", {"mode": "fake"}

    def fake_eval_phase(*, node_id: str, user_answer: str, mirror_answer: str | None, **kwargs):
        return EvalPhase(
            node_id=node_id,
            user_answer=user_answer,
            mirror_answer=mirror_answer,
            evaluation="enough for closure",
            gaps="",
            next_action="CLOSE_NODE",
            next_question=None,
            prompt_meta={"turn_kind": "eval"},
        )

    monkeypatch.setattr(session_loop, "run_teach_phase", fake_teach_phase)
    monkeypatch.setattr(session_loop, "run_mirror_prediction", fake_mirror_prediction)
    monkeypatch.setattr(session_loop, "run_eval_phase", fake_eval_phase)

    report, updated_graph = session_loop.run_session(
        session_id="session-bug-07",
        cfg=XYZGLConfig(),
        seed=11,
        max_turns=5,
        graph=_single_node_graph(confidence=0.75),
        input_provider=lambda prompt: ("fit and gap", {"typing_ms": 800}),
    )

    assert len(report.turns) == 1
    assert report.turns[0].eval.next_action == "CLOSE_NODE"
    assert updated_graph.get("joint_fitup").confidence == 1.0


def test_run_session_skips_turns_when_graph_starts_fully_mastered() -> None:
    report, updated_graph = session_loop.run_session(
        session_id="session-bug-07-initial-complete",
        cfg=XYZGLConfig(),
        seed=5,
        max_turns=3,
        graph=_single_node_graph(confidence=1.0),
        input_provider=lambda prompt: ("unused", {}),
    )

    assert report.turns == []
    assert updated_graph.get("joint_fitup").confidence == 1.0
