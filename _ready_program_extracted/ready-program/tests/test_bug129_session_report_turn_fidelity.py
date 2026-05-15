from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.orchestrator.phases import EvalPhase, TeachPhase
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator import session_loop


def _single_node_graph() -> KnowledgeGraph:
    return KnowledgeGraph(
        nodes=[
            Node(
                node_id="joint_fitup",
                title="Joint fit-up",
                summary="Explain fit-up and why gap control matters before welding.",
                required_keywords=["fit", "gap"],
                confidence=0.0,
            )
        ]
    )


def test_run_session_preserves_all_executed_turns_beyond_128(monkeypatch) -> None:
    budget = TeachingBudget(min_sentences=1, max_sentences=1, density="light")

    def fake_teach_phase(*, node_id: str, user_state: str, **kwargs):
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block="Keep going.",
            question="What is fit-up?",
            prompt_meta={"turn_kind": "teach"},
        )

    def fake_probe_phase(*, node_id: str, user_state: str, pointed_question: str, **kwargs):
        return TeachPhase(
            node_id=node_id,
            user_state=user_state,
            budget=budget,
            teaching_block="Try again.",
            question=pointed_question,
            prompt_meta={"turn_kind": "probe"},
        )

    def fake_mirror_prediction(**kwargs):
        return "mirror", {"mode": "fake"}

    def fake_eval_phase(
        *,
        node_id: str,
        user_answer: str,
        mirror_answer: str | None,
        turn_index: int,
        **kwargs,
    ):
        return EvalPhase(
            node_id=node_id,
            user_answer=user_answer,
            mirror_answer=mirror_answer,
            evaluation="needs more detail",
            gaps="explain the concept",
            next_action="PROBE",
            next_question=f"Probe question {turn_index + 1}?",
            prompt_meta={"turn_kind": "eval"},
        )

    monkeypatch.setattr(session_loop, "run_teach_phase", fake_teach_phase)
    monkeypatch.setattr(session_loop, "run_probe_phase", fake_probe_phase)
    monkeypatch.setattr(session_loop, "run_mirror_prediction", fake_mirror_prediction)
    monkeypatch.setattr(session_loop, "run_eval_phase", fake_eval_phase)

    report, _ = session_loop.run_session(
        session_id="session-bug-129",
        cfg=XYZGLConfig(),
        seed=7,
        max_turns=130,
        graph=_single_node_graph(),
        input_provider=lambda prompt: ("still learning", {"typing_ms": 1000}),
    )

    exported = report.to_json()

    assert len(report.turns) == 130
    assert len(exported["turns"]) == 130
    assert exported["turns"][0]["turn_index"] == 0
    assert exported["turns"][-1]["turn_index"] == 129
    assert exported["turns"][-1]["teach"]["question"] == "Probe question 129?"
    assert exported["turns"][-1]["eval"]["next_question"] == "Probe question 130?"
