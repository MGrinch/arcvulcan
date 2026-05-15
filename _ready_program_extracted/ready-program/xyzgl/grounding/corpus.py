from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

MAX_MANIFEST_BYTES = 1_000_000
MAX_SOURCES = 500
MAX_SOURCE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 100_000_000
MAX_PASSAGES = 20_000

_SAFE_SOURCE_ID = re.compile(r"[^A-Za-z0-9._-]+")
_UNSAFE_SOURCE_TITLE = re.compile(r"[\x00-\x1f\x7f\[\]<>]+")


def _collapse_spaces(text: str) -> str:
    return " ".join(str(text or "").split())


def sanitize_source_id(value: str) -> str:
    cleaned = _collapse_spaces(value)
    cleaned = _SAFE_SOURCE_ID.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned


def sanitize_source_title(value: str) -> str:
    cleaned = _collapse_spaces(value)
    cleaned = _UNSAFE_SOURCE_TITLE.sub(" ", cleaned)
    return _collapse_spaces(cleaned)


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


@dataclass(frozen=True)
class SourceSpec:
    id: str
    title: str
    path: str
    tags: list[str]
    license: str


@dataclass(frozen=True)
class Passage:
    source_id: str
    source_title: str
    text: str
    ordinal: int


@dataclass(frozen=True)
class Corpus:
    sources: list[SourceSpec]
    passages: list[Passage]
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _resolve_within(root: Path, rel_path: str) -> Path | None:
    candidate = Path((rel_path or "").strip())
    if not candidate or str(candidate) in {"", "."}:
        return None
    if candidate.is_absolute():
        return None
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except Exception:
        return None
    return resolved


def _hard_split_overlap(max_chars: int) -> int:
    if max_chars <= 1:
        return 0
    return max(1, min(160, max_chars // 5, max_chars - 1))


def _snap_split_end(text: str, start: int, max_chars: int) -> int:
    end = min(len(text), start + max_chars)
    if end >= len(text):
        return len(text)
    search_floor = start + max(1, max_chars // 2)
    if search_floor < end:
        split_at = text.rfind(" ", search_floor, end + 1)
        if split_at > start:
            return split_at
    return end


def _trim_overlap_prefix(text: str, start: int, end: int, max_chars: int) -> int:
    if start <= 0 or start >= end:
        return start
    prev_char = text[start - 1]
    cur_char = text[start]
    if not (prev_char.isalnum() and cur_char.isalnum()):
        return start
    search_limit = min(end, start + max(1, min(160, max_chars // 4)))
    next_space = text.find(" ", start, search_limit)
    if next_space < 0:
        return start
    trimmed = next_space + 1
    return trimmed if trimmed < end else start


def _split_hard(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        return []
    out: list[str] = []
    overlap = _hard_split_overlap(max_chars)
    start = 0
    n = len(text)
    while start < n:
        end = _snap_split_end(text, start, max_chars)
        if end <= start:
            end = min(n, start + max_chars)
            if end <= start:
                break
        chunk_start = _trim_overlap_prefix(text, start, end, max_chars)
        part = text[chunk_start:end].strip()
        if part:
            out.append(part)
        if end >= n:
            break
        next_start = max(0, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start
    return out


def _iter_paragraphs(text: str):
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    for chunk in re.split(r"\n(?:[ \t]*\n)+", normalized):
        p = chunk.strip()
        if p:
            yield p


def _chunk_text(text: str, *, max_chars: int = 800) -> list[str]:
    """Deterministic chunking with soft overlap on hard splits.

    Paragraph boundaries are preserved when possible. Oversized paragraphs are
    split into stable windows with a small deterministic overlap so evidence
    near a window boundary remains retrievable.
    """
    if max_chars <= 0:
        return []
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in _iter_paragraphs(text):
        if len(p) > max_chars:
            if cur:
                out.append("\n\n".join(cur).strip())
                cur = []
                cur_len = 0
            out.extend(_split_hard(p, max_chars))
            continue
        if cur_len + len(p) + 2 > max_chars and cur:
            out.append("\n\n".join(cur).strip())
            cur = [p]
            cur_len = len(p)
        else:
            cur.append(p)
            cur_len += len(p) + 2
    if cur:
        out.append("\n\n".join(cur).strip())
    return out


def _read_text_limited(path: Path, max_bytes: int) -> str | None:
    try:
        st = path.stat()
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    if st.st_size < 0 or st.st_size > max_bytes:
        return None
    with path.open("rb") as f:
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        return None
    return data.decode("utf-8", errors="replace")


def _manifest_error_corpus(*, code: str, detail: str | None = None) -> Corpus:
    warning = code if not detail else f"{code}:{detail}"
    stats = {"manifest_error": code}
    if detail:
        stats["manifest_error_detail"] = detail
    return Corpus(sources=[], passages=[], warnings=[warning], stats=stats)


def load_corpus(grounding_dir: Path) -> Corpus:
    """Load a local curriculum corpus.

    Expected:
      - grounding_dir/manifest.json
      - grounding_dir/<source.path> files

    Returns an empty corpus if manifest is missing.
    """
    manifest_path = grounding_dir / "manifest.json"
    if not manifest_path.exists():
        return Corpus(sources=[], passages=[])

    try:
        manifest_stat = manifest_path.stat()
    except OSError:
        manifest_stat = None
    if manifest_stat is not None:
        manifest_size = int(manifest_stat.st_size)
        if manifest_size > MAX_MANIFEST_BYTES:
            return _manifest_error_corpus(code="manifest_too_large", detail=f"{manifest_size}>{MAX_MANIFEST_BYTES}")

    manifest_text = _read_text_limited(manifest_path, MAX_MANIFEST_BYTES)
    if manifest_text is None:
        return Corpus(sources=[], passages=[])
    try:
        data = json.loads(manifest_text, object_pairs_hook=_no_duplicate_pairs)
    except ValueError as exc:
        detail = str(exc).strip()
        if detail.startswith("duplicate key:"):
            return _manifest_error_corpus(code="manifest_parse_error", detail=detail)
        return Corpus(sources=[], passages=[])
    except Exception:
        return Corpus(sources=[], passages=[])
    raw_sources = data.get("sources") or []
    if not isinstance(raw_sources, list):
        raw_sources = []
    sources: list[SourceSpec] = []
    passages: list[Passage] = []
    source_chunks: list[tuple[SourceSpec, list[str]]] = []
    total_loaded_bytes = 0
    seen_source_ids: set[str] = set()
    warnings: list[str] = []
    capped_sources = raw_sources[:MAX_SOURCES]
    skipped_current_source_passages = 0
    remaining_manifest_sources = 0
    omitted_passages = 0
    truncated_sources_due_to_passage_cap = 0

    manifest_source_count = len(raw_sources)
    if manifest_source_count > MAX_SOURCES:
        warnings.append(f"source_limit_exceeded:{manifest_source_count}>{MAX_SOURCES}")

    for s in capped_sources:
        if not isinstance(s, dict):
            continue
        raw_sid = str(s.get("id") or "").strip()
        sid = sanitize_source_id(raw_sid)
        if not sid or sid in seen_source_ids:
            continue
        seen_source_ids.add(sid)
        raw_tags = s.get("tags") or []
        title = sanitize_source_title(str(s.get("title") or raw_sid or sid)) or sid
        spec = SourceSpec(
            id=sid,
            title=title,
            path=str(s.get("path") or ""),
            tags=[str(t) for t in raw_tags] if isinstance(raw_tags, list) else [],
            license=str(s.get("license") or ""),
        )
        sources.append(spec)

        fpath = _resolve_within(grounding_dir, spec.path)
        if fpath is None or not fpath.exists() or not fpath.is_file():
            continue
        try:
            fst = fpath.stat()
        except OSError:
            continue
        if not stat.S_ISREG(fst.st_mode):
            continue
        size = int(fst.st_size)
        if size < 0:
            continue
        if size > MAX_SOURCE_BYTES:
            continue
        if total_loaded_bytes + size > MAX_TOTAL_BYTES:
            break
        text = _read_text_limited(fpath, MAX_SOURCE_BYTES)
        if text is None:
            continue
        total_loaded_bytes += size
        source_chunks.append((spec, _chunk_text(text)))

    if source_chunks:
        chunk_positions = [0] * len(source_chunks)
        limit_hit_index: int | None = None
        while len(passages) < MAX_PASSAGES:
            progressed = False
            for source_index, (spec, chunks) in enumerate(source_chunks):
                chunk_index = chunk_positions[source_index]
                if chunk_index >= len(chunks):
                    continue
                passages.append(
                    Passage(source_id=spec.id, source_title=spec.title, text=chunks[chunk_index], ordinal=chunk_index)
                )
                chunk_positions[source_index] = chunk_index + 1
                progressed = True
                if len(passages) >= MAX_PASSAGES:
                    limit_hit_index = source_index
                    skipped_current_source_passages = max(0, len(chunks) - chunk_positions[source_index])
                    break
            if not progressed:
                break

        if len(passages) >= MAX_PASSAGES:
            remaining_with_chunks = 0
            for source_index, (_spec, chunks) in enumerate(source_chunks):
                remaining = max(0, len(chunks) - chunk_positions[source_index])
                if remaining <= 0:
                    continue
                truncated_sources_due_to_passage_cap += 1
                omitted_passages += remaining
                if limit_hit_index is not None and source_index > limit_hit_index:
                    remaining_with_chunks += 1
            remaining_manifest_sources = remaining_with_chunks
            if omitted_passages > 0:
                warnings.append(
                    "passage_limit_exhausted:"
                    f"{len(passages)}>={MAX_PASSAGES};"
                    f"truncated_current_source_passages={skipped_current_source_passages};"
                    f"remaining_manifest_sources={remaining_manifest_sources};"
                    f"truncated_sources={truncated_sources_due_to_passage_cap};"
                    f"omitted_passages={omitted_passages};"
                    "allocation=round_robin_by_source"
                )

    stats = {
        "manifest_source_count": manifest_source_count,
        "loaded_source_specs": len(sources),
        "loaded_passages": len(passages),
        "max_sources": MAX_SOURCES,
        "max_passages": MAX_PASSAGES,
        "truncated_source_count": max(0, manifest_source_count - MAX_SOURCES),
        "truncated_current_source_passages_due_to_passage_cap": skipped_current_source_passages,
        "remaining_manifest_sources_due_to_passage_cap": remaining_manifest_sources,
        "truncated_sources_due_to_passage_cap": truncated_sources_due_to_passage_cap,
        "omitted_passages_due_to_passage_cap": omitted_passages,
        "passage_allocation_strategy": "round_robin_by_source",
    }
    return Corpus(sources=sources, passages=passages, warnings=warnings, stats=stats)
