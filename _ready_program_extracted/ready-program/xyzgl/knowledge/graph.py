from __future__ import annotations

import json
import math
import os
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path


SCHEMA_VERSION = "knowledge_graph@1"
MAX_GRAPH_BYTES = 5_000_000
MAX_GRAPH_NODES = 20_000
MAX_TITLE_CHARS = 200
MAX_SUMMARY_CHARS = 4_000
MAX_KEYWORDS_PER_NODE = 128
MAX_FLAGS_PER_NODE = 128
MAX_TOKEN_CHARS = 80


class GraphLoadError(ValueError):
    """Raised when an explicit on-disk graph exists but cannot be loaded safely."""


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


@dataclass(frozen=True)
class Node:
    """A single teach/assess unit.

    `summary` should be short (≈250 chars) so the Tutor can reason over it.
    `required_keywords` is used by deterministic closure heuristics.
    """

    node_id: str
    title: str
    summary: str
    required_keywords: list[str]
    confidence: float = 0.0
    fragility_flags: list[str] = field(default_factory=list)
    last_verified_turn: int = -1

    def with_update(self, **kw) -> "Node":
        return replace(self, **kw)


@dataclass(frozen=True)
class KnowledgeGraph:
    nodes: list[Node]
    _index: dict[str, Node] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_index", {n.node_id: n for n in self.nodes if n.node_id})

    def get(self, node_id: str) -> Node | None:
        return self._index.get(node_id)

    def upsert(self, node: Node) -> "KnowledgeGraph":
        if not node.node_id:
            return self

        out: list[Node] = []
        replaced = False
        for n in self.nodes:
            if n.node_id == node.node_id:
                if not replaced:
                    out.append(node)
                    replaced = True
                # Drop duplicates for the same node_id while rewriting.
            else:
                out.append(n)
        if replaced:
            return KnowledgeGraph(nodes=out)

        # Maintain sorted order without resorting the entire list.
        lo, hi = 0, len(out)
        while lo < hi:
            mid = (lo + hi) // 2
            if out[mid].node_id < node.node_id:
                lo = mid + 1
            else:
                hi = mid
        out.insert(lo, node)
        return KnowledgeGraph(nodes=out)


def default_graph() -> KnowledgeGraph:
    """Small seed graph that matches the repo's current demo curriculum."""
    nodes = [
        Node(
            node_id="pos_1f_vs_2f",
            title="Fillet positions: 1F vs 2F",
            summary=(
                "Explain what 1F (flat fillet) and 2F (horizontal fillet) mean, how gravity affects the puddle, "
                "and the main technique changes (angle, travel, pause)."
            ),
            required_keywords=["1f", "2f", "gravity"],
            confidence=0.0,
            fragility_flags=[],
        ),
        Node(
            node_id="fitup_tacking",
            title="Fit-up and tacking discipline",
            summary=(
                "Describe why uneven fit-up and inconsistent gaps lead to defects, and what to do before welding "
                "(grind/trim, align, consistent tack spacing)."
            ),
            required_keywords=["fit", "gap", "tack"],
            confidence=0.0,
            fragility_flags=[],
        ),
        Node(
            node_id="smaw_basic_arc",
            title="SMAW arc length and stability",
            summary=(
                "Explain arc length, why it matters for penetration and spatter, and what changes when arc is too long "
                "or too short."
            ),
            required_keywords=["arc", "length"],
            confidence=0.0,
            fragility_flags=[],
        ),
    ]
    nodes.sort(key=lambda n: n.node_id)
    return KnowledgeGraph(nodes=nodes)


def _finite_confidence(value: object) -> float:
    try:
        cf = float(value)
    except Exception:
        return 0.0
    if not math.isfinite(cf):
        return 0.0
    if cf < 0.0:
        return 0.0
    if cf > 1.0:
        return 1.0
    return cf


def _merge_nodes(existing: Node, incoming: Node) -> Node:
    req = sorted(set(existing.required_keywords or []) | set(incoming.required_keywords or []))[:MAX_KEYWORDS_PER_NODE]
    flags = sorted(set(existing.fragility_flags or []) | set(incoming.fragility_flags or []))[:MAX_FLAGS_PER_NODE]
    return Node(
        node_id=existing.node_id,
        title=existing.title or incoming.title,
        summary=existing.summary or incoming.summary,
        required_keywords=req,
        confidence=min(_finite_confidence(existing.confidence), _finite_confidence(incoming.confidence)),
        fragility_flags=flags,
        last_verified_turn=max(int(existing.last_verified_turn), int(incoming.last_verified_turn)),
    )


def _safe_text(value: object, *, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def _safe_token_list(values: object, *, max_items: int) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:max_items]:
        t = _safe_text(raw, max_chars=MAX_TOKEN_CHARS)
        if t:
            out.append(t)
    return out


def _canonical_node_id(value: object) -> str:
    return str(value or "").strip()


def _persist_node_id(node_id: object, *, seen: set[str]) -> str:
    persisted = str(node_id or "")
    canonical = _canonical_node_id(persisted)
    if not canonical:
        raise ValueError("node_id must be non-empty")
    if persisted != canonical:
        raise ValueError(f"node_id must not change during persistence: {persisted!r}")
    if canonical in seen:
        raise ValueError(f"node_id collides on reload: {canonical!r}")
    seen.add(canonical)
    return persisted


def _validate_loaded_node_id(node_id: object, *, seen: set[str], path: Path) -> str:
    persisted = str(node_id or "")
    canonical = _canonical_node_id(persisted)
    if not canonical:
        raise GraphLoadError(f"invalid graph file: node_id must be non-empty: {path}")
    if persisted != canonical:
        raise GraphLoadError(
            f"invalid graph file: node_id must not change on reload: {persisted!r}: {path}"
        )
    if canonical in seen:
        raise GraphLoadError(f"invalid graph file: node_id collides on reload: {canonical!r}: {path}")
    seen.add(canonical)
    return canonical


def load_graph(path: Path) -> KnowledgeGraph:
    if not path.exists():
        return default_graph()
    try:
        graph_size = int(path.stat().st_size)
    except OSError as exc:
        raise GraphLoadError(f"could not stat graph file: {path}") from exc
    if graph_size > MAX_GRAPH_BYTES:
        raise GraphLoadError(
            f"graph file exceeds maximum size: {graph_size} > {MAX_GRAPH_BYTES}: {path}"
        )
    try:
        data = json.loads(
            path.read_text(encoding="utf-8", errors="replace"),
            object_pairs_hook=_no_duplicate_pairs,
        )
    except Exception as exc:
        raise GraphLoadError(f"invalid graph file: {path}") from exc
    raw_nodes = data.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raw_nodes = []
    loaded_nodes: list[Node] = []
    seen_node_ids: set[str] = set()
    for rn in raw_nodes[:MAX_GRAPH_NODES]:
        if not isinstance(rn, dict):
            continue
        nid = _validate_loaded_node_id(rn.get("node_id"), seen=seen_node_ids, path=path)
        required_keywords = _safe_token_list(rn.get("required_keywords") or [], max_items=MAX_KEYWORDS_PER_NODE)
        fragility_flags = _safe_token_list(rn.get("fragility_flags") or [], max_items=MAX_FLAGS_PER_NODE)
        raw_last_verified = rn.get("last_verified_turn")
        try:
            last_verified_turn = -1 if raw_last_verified is None else int(raw_last_verified)
        except Exception:
            last_verified_turn = -1
        loaded_nodes.append(
            Node(
                node_id=nid,
                title=_safe_text(rn.get("title") or nid, max_chars=MAX_TITLE_CHARS),
                summary=_safe_text(rn.get("summary") or "", max_chars=MAX_SUMMARY_CHARS),
                required_keywords=required_keywords,
                confidence=_finite_confidence(rn.get("confidence")),
                fragility_flags=fragility_flags,
                last_verified_turn=last_verified_turn,
            )
        )
    nodes = sorted(loaded_nodes, key=lambda n: n.node_id)
    return KnowledgeGraph(nodes=nodes)


def _dedup_nodes(nodes: list[Node]) -> list[Node]:
    by_id: dict[str, Node] = {}
    for n in nodes:
        if not n.node_id:
            continue
        prev = by_id.get(n.node_id)
        by_id[n.node_id] = n if prev is None else _merge_nodes(prev, n)
    return sorted(by_id.values(), key=lambda n: n.node_id)


def save_graph(graph: KnowledgeGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_nodes = _dedup_nodes(list(graph.nodes or []))[:MAX_GRAPH_NODES]
    seen_node_ids: set[str] = set()
    node_rows = []
    for n in safe_nodes:
        node_rows.append(
            {
                "node_id": _persist_node_id(n.node_id, seen=seen_node_ids),
                "title": _safe_text(n.title, max_chars=MAX_TITLE_CHARS),
                "summary": _safe_text(n.summary, max_chars=MAX_SUMMARY_CHARS),
                "required_keywords": _safe_token_list(n.required_keywords, max_items=MAX_KEYWORDS_PER_NODE),
                "confidence": _finite_confidence(n.confidence),
                "fragility_flags": _safe_token_list(n.fragility_flags, max_items=MAX_FLAGS_PER_NODE),
                "last_verified_turn": int(n.last_verified_turn),
            }
        )
    obj = {
        "schema_version": SCHEMA_VERSION,
        "nodes": node_rows,
    }
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(tmp), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            fd = None
            json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
