from __future__ import annotations

import math
from dataclasses import replace

from .graph import KnowledgeGraph, Node


def _finite_conf(value: object) -> float:
    try:
        x = float(value)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _finite_nonnegative(value: object) -> float:
    try:
        x = float(value)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return x if x >= 0.0 else 0.0


def close_node(
    graph: KnowledgeGraph,
    node_id: str,
    *,
    turn_index: int,
    confidence_bump: float = 0.25,
    resonance_confidence: float | None = None,
) -> KnowledgeGraph:
    """Mark a node as verified/closed.

    Policy:
      - Increase confidence by `confidence_bump` (cap at 1.0)
      - If `resonance_confidence` is provided, use it instead of `confidence_bump`
      - Update last_verified_turn
    """
    n = graph.get(node_id)
    if n is None:
        return graph
    old_conf = _finite_conf(n.confidence)
    bump_source = resonance_confidence if resonance_confidence is not None else confidence_bump
    bump = _finite_nonnegative(bump_source)
    new_conf = min(1.0, max(0.0, old_conf + bump))
    new_turn = max(int(n.last_verified_turn), int(turn_index))
    nn = replace(n, confidence=new_conf, last_verified_turn=new_turn)
    return graph.upsert(nn)


def update_mastery_from_resonance(
    graph: KnowledgeGraph,
    node_id: str,
    *,
    resonance: float,
    text_similarity: float,
    turn_index: int,
    high_resonance_threshold: float = 0.9,
    high_similarity_threshold: float = 0.95,
    mastery_increment: float = 0.1,
) -> KnowledgeGraph:
    """Gradually increase node mastery based on strong resonance or similarity.

    Policy:
      - If `resonance` exceeds `high_resonance_threshold`, increase confidence by `mastery_increment`
      - If `text_similarity` exceeds `high_similarity_threshold`, increase confidence by `mastery_increment`
      - Confidence is capped at 1.0
      - `last_verified_turn` is always updated to the latest turn seen
    """
    n = graph.get(node_id)
    if n is None:
        return graph

    old_conf = _finite_conf(n.confidence)
    safe_resonance = _finite_conf(resonance)
    safe_similarity = _finite_conf(text_similarity)
    increment = _finite_nonnegative(mastery_increment)

    should_increment = (
        safe_resonance > _finite_conf(high_resonance_threshold)
        or safe_similarity > _finite_conf(high_similarity_threshold)
    )
    new_conf = min(1.0, old_conf + increment) if should_increment else old_conf
    new_turn = max(int(n.last_verified_turn), int(turn_index))
    nn = replace(n, confidence=new_conf, last_verified_turn=new_turn)
    return graph.upsert(nn)


def mark_fragile(graph: KnowledgeGraph, node_id: str, *, flag: str) -> KnowledgeGraph:
    n = graph.get(node_id)
    if n is None:
        return graph
    flags = list(n.fragility_flags or [])
    if flag and flag not in flags:
        flags.append(flag)
    nn = replace(n, fragility_flags=flags)
    return graph.upsert(nn)
