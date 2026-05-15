from __future__ import annotations

from dataclasses import dataclass

from .policies import TeachingBudget


@dataclass(frozen=True)
class TeachPhase:
    node_id: str
    user_state: str
    budget: TeachingBudget
    teaching_block: str
    question: str
    prompt_meta: dict
    persona_injected: bool = False


@dataclass(frozen=True)
class EvalPhase:
    node_id: str
    user_answer: str
    mirror_answer: str | None
    evaluation: str
    gaps: str
    next_action: str  # "PROBE" | "CLOSE_NODE"
    next_question: str | None
    prompt_meta: dict
    resonance: float | None = None
    mastery: float | None = None
    text_similarity: float | None = None
