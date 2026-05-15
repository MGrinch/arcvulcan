from __future__ import annotations

import math
from itertools import groupby

from .graph import KnowledgeGraph, Node


def _score_confidence(v: object) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _rotate_tied_nodes(nodes: list[Node], *, seed: int | None) -> list[Node]:
    if len(nodes) <= 1 or seed is None:
        return list(nodes)
    offset = int(seed) % len(nodes)
    if offset == 0:
        return list(nodes)
    return list(nodes[offset:]) + list(nodes[:offset])


def select_next_node(graph: KnowledgeGraph, *, seed: int | None, avoid_node_id: str | None = None) -> Node:
    """Select the next node deterministically.

    Policy (v1):
      1) Prefer lowest confidence
      2) Break confidence ties by rotating equally scored candidates with `seed`
      3) If `avoid_node_id` is provided and there is an alternative, avoid repeating it

    This keeps runs reproducible for the same seed while allowing different seeds
    to explore equally eligible nodes in different orders. When `seed` is ``None``,
    ordering falls back to plain lexicographic tie-breaking for backwards compatibility.
    """
    if not graph.nodes:
        raise ValueError("graph has no nodes")

    base = sorted(graph.nodes, key=lambda n: (_score_confidence(n.confidence), n.node_id))
    ordered: list[Node] = []
    for _, tied in groupby(base, key=lambda n: _score_confidence(n.confidence)):
        ordered.extend(_rotate_tied_nodes(list(tied), seed=seed))

    # Avoid immediate repeats if possible
    if avoid_node_id and len(ordered) > 1 and ordered[0].node_id == avoid_node_id:
        ordered = ordered[1:] + ordered[:1]

    return ordered[0]
