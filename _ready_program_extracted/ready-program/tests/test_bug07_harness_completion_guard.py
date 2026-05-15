from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import harness_session
from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.orchestrator.phases import EvalPhase, TeachPhase
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.session_loop import TurnRecord


def _graph(*, confidence: float) -> KnowledgeGraph:
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


def _turn(turn_index: int, *, next_action: str = "PROBE") -> TurnRecord:
    budget = TeachingBudget(min_sentences=1, max_sentences=1, density="light")
    return TurnRecord(
        turn_index=turn_index,
        node_id="joint_fitup",
        node_title="Joint fit-up",
        user_state="flow",
        teach=TeachPhase(
            node_id="joint_fitup",
            user_state="flow",
            budget=budget,
            teaching_block="Short lesson.",
            question="What matters in fit-up?",
            prompt_meta={},
        ),
        mirror_answer=None,
        mirror_meta=None,
        eval=EvalPhase(
            node_id="joint_fitup",
            user_answer="fit and gap",
            mirror_answer=None,
            evaluation="ok",
            gaps="",
            next_action=next_action,
            next_question=None,
            prompt_meta={},
        ),
    )


def test_completion_guard_requires_true_full_mastery_not_single_close() -> None:
    completion_turn = harness_session._first_graph_completion_turn(
        _graph(confidence=0.0),
        [_turn(0, next_action="CLOSE_NODE")],
    )

    assert completion_turn is None


def test_completion_guard_detects_real_post_mastery_overrun() -> None:
    terminal = harness_session._classify_session_terminal_state(
        _graph(confidence=0.75),
        _graph(confidence=1.0),
        [_turn(0, next_action="CLOSE_NODE"), _turn(1, next_action="PROBE")],
    )

    assert terminal["completion_turn_index"] == 0
    assert terminal["post_completion_turns"] == [1]
    assert terminal["terminal_state"] == "post_mastery_overrun"
