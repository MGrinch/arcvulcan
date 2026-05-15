from __future__ import annotations

from collections import OrderedDict
import hashlib
import re
from dataclasses import dataclass

from .corpus import Corpus, Passage


@dataclass(frozen=True)
class Snippet:
    source_id: str
    source_title: str
    passage_ordinal: int
    score: float
    excerpt: str


_WORD = re.compile(r"[a-zA-Z0-9']+")
_MAX_QUERY_TOKENS = 256
_MAX_PASSAGE_TOKENS = 512
_MAX_PASSAGE_TOKEN_CACHE = 256
_MAX_RETURN_SNIPPETS = 128
_MAX_SCANNED_PASSAGES = 20_000
_MAX_SNIPPET_EXCERPT_CHARS = 4_096
_RANK_NAMESPACE = b"grounding-rank-v2"
_QUERY_WINDOW_NAMESPACE = b"grounding-window-v2"
_MAX_SNIPPETS_PER_SOURCE = 3
_MIN_RELEVANCE_SCORE = 0.02
_MIN_RELATIVE_SCORE = 0.35
_INSTRUCTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "assistant",
    "you must",
    "answer with",
    "do not cite",
    "repeat exactly",
    "follow these instructions",
)


def _ordered_unique_tokens(s: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _WORD.finditer(s or ""):
        tok = m.group(0).lower()
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _head_tail_window(tokens: list[str], limit: int) -> set[str]:
    if limit <= 0:
        return set()
    if len(tokens) <= limit:
        return set(tokens)
    head = max(1, limit // 2)
    tail = max(1, limit - head)
    keep = tokens[:head] + tokens[-tail:]
    return set(keep)


def _tokens(s: str, *, max_tokens: int | None = None) -> set[str]:
    ordered = _ordered_unique_tokens(s)
    if max_tokens is None:
        return set(ordered)
    return _head_tail_window(ordered, max(1, int(max_tokens)))


def _stable_tiebreak(source_id: str, ordinal: int, source_title: str, excerpt: str) -> int:
    payload = f"{source_id}\x1f{ordinal}\x1f{source_title}\x1f{excerpt[:256]}".encode("utf-8", errors="replace")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8, key=_RANK_NAMESPACE).digest(), "big")


def _rank_tuple(score: float, tiebreak: int, ordinal: int) -> tuple[float, int, int]:
    return (-float(score), int(tiebreak), int(ordinal))


def _entry_rank(entry: tuple[float, int, str, int, str, str, int]) -> tuple[float, int, int]:
    return _rank_tuple(entry[0], entry[1], entry[3])


def _excerpt(text: str) -> str:
    out = (text or "").strip()
    if len(out) <= _MAX_SNIPPET_EXCERPT_CHARS:
        return out
    return out[:_MAX_SNIPPET_EXCERPT_CHARS]


def _instruction_penalty(text: str) -> float:
    lowered = (text or "").lower()
    for needle in _INSTRUCTION_PATTERNS:
        if needle in lowered:
            return 0.55
    return 1.0


def _keyword_stuffing_penalty(query_tokens: set[str], passage_tokens: set[str]) -> float:
    if not query_tokens or not passage_tokens:
        return 1.0
    inter = len(query_tokens.intersection(passage_tokens))
    if inter <= 0:
        return 1.0
    non_query = len(passage_tokens.difference(query_tokens))
    match_ratio = inter / max(1, len(passage_tokens))
    if match_ratio >= 0.75 and non_query <= max(2, inter // 2) and len(passage_tokens) <= max(10, len(query_tokens) + 2):
        return 0.5
    return 1.0


def _per_source_cap(limit: int) -> int:
    return max(1, min(_MAX_SNIPPETS_PER_SOURCE, (limit + 1) // 2))


def _diversify(entries: list[tuple[float, int, str, int, str, str, int]], limit: int) -> list[tuple[float, int, str, int, str, str, int]]:
    if limit <= 0 or not entries:
        return []
    ranked = sorted(entries, key=_entry_rank)
    grouped: OrderedDict[str, list[tuple[float, int, str, int, str, str, int]]] = OrderedDict()
    for entry in ranked:
        grouped.setdefault(entry[2], []).append(entry)
    selected: list[tuple[float, int, str, int, str, str, int]] = []
    cap = _per_source_cap(limit)
    for depth in range(cap):
        for sid in grouped:
            source_entries = grouped[sid]
            if depth >= len(source_entries):
                continue
            selected.append(source_entries[depth])
            if len(selected) >= limit:
                return selected
    for entry in ranked:
        if len(selected) >= limit:
            break
        if entry in selected:
            continue
        selected.append(entry)
    return selected


def _filter_weak_matches(entries: list[tuple[float, int, str, int, str, str, int]], q_len: int) -> list[tuple[float, int, str, int, str, str, int]]:
    if not entries:
        return []
    top_score = max(float(entry[0]) for entry in entries)
    if top_score < _MIN_RELEVANCE_SCORE:
        # Preserve a solitary exact-ish rare-token hit instead of turning a
        # legitimate one-source corpus lookup into an empty result set.
        if len(entries) == 1 and int(entries[0][6]) >= 1 and top_score > 0:
            return list(entries)
        return []
    min_relative = max(_MIN_RELEVANCE_SCORE, round(top_score * _MIN_RELATIVE_SCORE, 4))
    keep: list[tuple[float, int, str, int, str, str, int]] = []
    for entry in entries:
        score = float(entry[0])
        inter = int(entry[6])
        if score >= min_relative:
            keep.append(entry)
            continue
        if inter >= min(3, max(1, q_len)) and score >= _MIN_RELEVANCE_SCORE:
            keep.append(entry)
    return keep


def retrieve_snippets(corpus: Corpus, query: str, *, max_snippets: int = 6) -> list[Snippet]:
    """Deterministic lexical retrieval with poisoning mitigations.

    Score = Jaccard overlap between query tokens and passage tokens, adjusted to
    reduce instruction-like and keyword-stuffed snippets. Candidate ordering is
    deterministic but does not privilege lexicographically small source ids.
    Returned snippets are diversified across sources when possible.
    """
    limit = max(0, min(_MAX_RETURN_SNIPPETS, int(max_snippets)))
    if limit <= 0:
        return []

    q = _tokens(query, max_tokens=_MAX_QUERY_TOKENS)
    if not q or not corpus.passages:
        return []
    q_len = len(q)

    candidates: list[tuple[float, int, str, int, str, str, int]] = []
    token_cache: OrderedDict[str, set[str]] = OrderedDict()
    for idx, p in enumerate(corpus.passages):
        if idx >= _MAX_SCANNED_PASSAGES:
            break
        pt = token_cache.get(p.text)
        if pt is None:
            pt = _tokens(p.text, max_tokens=_MAX_PASSAGE_TOKENS)
            token_cache[p.text] = pt
            if len(token_cache) > _MAX_PASSAGE_TOKEN_CACHE:
                token_cache.popitem(last=False)
        else:
            token_cache.move_to_end(p.text)
        if not pt:
            continue
        inter = len(q.intersection(pt))
        if inter <= 0:
            continue
        union = q_len + len(pt) - inter
        base = (inter / union) if union > 0 else 0.0
        score = base * _instruction_penalty(p.text) * _keyword_stuffing_penalty(q, pt)
        score4 = round(float(score), 4)
        if score4 <= 0:
            continue
        excerpt = _excerpt(p.text)
        candidates.append((score4, _stable_tiebreak(p.source_id, p.ordinal, p.source_title, excerpt), p.source_id, p.ordinal, p.source_title, excerpt, inter))

    filtered = _filter_weak_matches(candidates, q_len)
    chosen = _diversify(filtered, limit)
    out: list[Snippet] = []
    for score4, _tie, sid, ord_, title, excerpt, _inter in chosen:
        out.append(
            Snippet(
                source_id=sid,
                source_title=title,
                passage_ordinal=ord_,
                score=score4,
                excerpt=excerpt,
            )
        )
    return out
