from __future__ import annotations

from collections import OrderedDict
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Tuple

from .corpus import (
    MAX_MANIFEST_BYTES,
    MAX_SOURCES,
    Corpus,
    _no_duplicate_pairs,
    _resolve_within,
    load_corpus,
    sanitize_source_id,
    sanitize_source_title,
)
from .retrieval import retrieve_snippets

_CORPUS_CACHE_MAX_ENTRIES = 8
MAX_SNIPPET_EXCERPT_CHARS = 4_096
MAX_HEADER_SOURCE_ID_CHARS = 64
MAX_HEADER_SOURCE_TITLE_CHARS = 120
_CACHE_KEY_NAMESPACE = "grounding-cache-v2"
_CORPUS_CACHE: OrderedDict[str, Tuple[str, Corpus]] = OrderedDict()


def _manifest_signature(manifest: Path) -> tuple[int, int]:
    try:
        st = manifest.stat()
    except OSError:
        return (0, 0)
    return (int(getattr(st, "st_mtime_ns", 0) or 0), int(getattr(st, "st_size", 0) or 0))


def _corpus_signature(grounding_dir: Path) -> str:
    manifest = grounding_dir / "manifest.json"
    hasher = hashlib.sha256()
    manifest_mtime_ns, manifest_size = _manifest_signature(manifest)
    hasher.update(f"manifest:{manifest_mtime_ns}:{manifest_size}".encode("utf-8", errors="replace"))

    if manifest_size <= 0 or manifest_size > MAX_MANIFEST_BYTES:
        return hasher.hexdigest()

    try:
        manifest_text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hasher.hexdigest()
    if len(manifest_text.encode("utf-8")) > MAX_MANIFEST_BYTES:
        return hasher.hexdigest()
    try:
        data = json.loads(manifest_text, object_pairs_hook=_no_duplicate_pairs)
    except Exception:
        return hasher.hexdigest()

    raw_sources = data.get("sources") or []
    if not isinstance(raw_sources, list):
        return hasher.hexdigest()

    # Track every manifest-listed source so edits/deletions beyond the runtime
    # load cap still invalidate the in-process grounding cache.
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id") or "").strip()
        if not source_id:
            continue
        raw_path = str(source.get("path") or "")
        hasher.update(b"\0source\0")
        hasher.update(source_id.encode("utf-8", errors="replace"))
        hasher.update(b"\0")
        hasher.update(raw_path.encode("utf-8", errors="replace"))

        source_path = _resolve_within(grounding_dir, raw_path)
        if source_path is None:
            hasher.update(b"\0invalid")
            continue
        try:
            st = source_path.stat()
        except OSError:
            hasher.update(b"\0missing")
            continue
        source_mtime_ns = int(getattr(st, "st_mtime_ns", 0) or 0)
        source_size = int(getattr(st, "st_size", 0) or 0)
        hasher.update(f"\0present:{source_mtime_ns}:{source_size}".encode("utf-8", errors="replace"))

    return hasher.hexdigest()


def _cache_key(grounding_dir: Path) -> str:
    resolved = str(grounding_dir.resolve())
    return hashlib.sha256(f"{_CACHE_KEY_NAMESPACE}:{resolved}".encode("utf-8", errors="replace")).hexdigest()


def _elide_middle(text: str, *, max_chars: int, marker: str) -> str:
    s = str(text or "").strip()
    limit = max(0, int(max_chars))
    if limit <= 0:
        return ""
    if len(s) <= limit:
        return s
    if limit <= len(marker):
        return s[:limit]
    head = max(1, (limit - len(marker)) // 2)
    tail = max(0, limit - len(marker) - head)
    if tail <= 0:
        return s[:limit]
    return f"{s[:head]}{marker}{s[-tail:]}"


def _render_snippet_header(source_id: str, source_title: str, passage_ordinal: int) -> str:
    safe_id = sanitize_source_id(source_id) or "source"
    safe_title = sanitize_source_title(source_title)
    compact_id = _elide_middle(safe_id, max_chars=MAX_HEADER_SOURCE_ID_CHARS, marker="--")
    compact_title = _elide_middle(safe_title, max_chars=MAX_HEADER_SOURCE_TITLE_CHARS, marker="...")
    label = f"[src:{compact_id}:{passage_ordinal}]"
    if compact_title:
        return f"{label} {compact_title}\n"
    return f"{label}\n"


def _cached_corpus(grounding_dir: Path) -> Corpus:
    # Cache by the full manifest-listed corpus footprint, not only manifest.json.
    key = _cache_key(grounding_dir)
    sig = _corpus_signature(grounding_dir)
    hit = _CORPUS_CACHE.get(key)
    if hit and hit[0] == sig:
        _CORPUS_CACHE.move_to_end(key)
        return hit[1]
    # Drop stale entry first to avoid retaining duplicate corpus buffers during refresh.
    _CORPUS_CACHE.pop(key, None)
    corpus = load_corpus(grounding_dir)
    _CORPUS_CACHE[key] = (sig, corpus)
    _CORPUS_CACHE.move_to_end(key)
    while len(_CORPUS_CACHE) > _CORPUS_CACHE_MAX_ENTRIES:
        _CORPUS_CACHE.popitem(last=False)
    return corpus


def build_grounding(grounding_dir: Path, query: str, *, max_snippets: int = 6, max_chars: int = 3000) -> tuple[str, dict]:
    """Return (grounding_text, meta)."""
    if max_snippets <= 0 or max_chars <= 0:
        return "", {
            "snippets": [],
            "grounding_dir": str(grounding_dir),
            "reason": "nonpositive_limits",
            "max_snippets": int(max_snippets),
            "max_chars": int(max_chars),
        }

    corpus = _cached_corpus(grounding_dir)
    snippets = retrieve_snippets(corpus, query, max_snippets=max_snippets)

    if not snippets:
        meta = {"snippets": [], "grounding_dir": str(grounding_dir)}
        if corpus.warnings:
            meta["warnings"] = list(corpus.warnings)
        if corpus.stats:
            meta["corpus_stats"] = dict(corpus.stats)
        return "", meta

    out = StringIO()
    used: list[dict] = []
    budget = int(max_chars)
    for sn in snippets:
        header = _render_snippet_header(sn.source_id, sn.source_title, sn.passage_ordinal)
        excerpt = (sn.excerpt or "").strip()
        if len(excerpt) > MAX_SNIPPET_EXCERPT_CHARS:
            excerpt = excerpt[:MAX_SNIPPET_EXCERPT_CHARS].rstrip()
        max_excerpt_chars = max(0, budget - len(header) - 1)
        if max_excerpt_chars <= 0:
            continue
        if len(excerpt) > max_excerpt_chars:
            excerpt = excerpt[:max_excerpt_chars].rstrip()
        if not excerpt:
            continue
        needed = len(header) + len(excerpt) + 1
        out.write(header)
        out.write(excerpt)
        out.write("\n")
        budget -= needed
        used.append(
            {
                "source_id": sn.source_id,
                "passage_ordinal": sn.passage_ordinal,
                "score": sn.score,
            }
        )
        if budget <= 0:
            break

    text = out.getvalue().strip()
    meta = {"snippets": used, "grounding_dir": str(grounding_dir)}
    if corpus.warnings:
        meta["warnings"] = list(corpus.warnings)
    if corpus.stats:
        meta["corpus_stats"] = dict(corpus.stats)
    return text, meta
