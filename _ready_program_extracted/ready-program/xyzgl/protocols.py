from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat

MAX_PROTOCOL_BYTES = 2_000_000


@dataclass(frozen=True)
class ProtocolBundle:
    text: str
    source_path: str
    loaded: bool
    load_error: str | None = None


def _fallback_bundle(rel_path: str, *, error: str) -> ProtocolBundle:
    return ProtocolBundle(
        text=(
            "ROLE PROTOCOL (fallback)\n"
            "- Orchestrator controls talk order.\n"
            "- Tutor teaches and audits reasoning; do not invent.\n"
            "- Mirror simulates learner; never teaches.\n"
        ),
        source_path=rel_path,
        loaded=False,
        load_error=error,
    )


def should_reground(turn_index: int, every_n_turns: int) -> bool:
    """Return True if protocol should be re-injected this turn.

    Policy:
      - Always reground on turn 0
      - If every_n_turns <= 0: reground only on turn 0
      - Else: reground on turns divisible by N (0, N, 2N, ...)
    """
    if turn_index <= 0:
        return True
    if every_n_turns <= 0:
        return False
    return (turn_index % every_n_turns) == 0


def _resolve_within(root: Path, rel_path: str) -> Path:
    raw = (rel_path or "").strip()
    if not raw or raw == ".":
        raise ValueError("empty protocol path is not allowed")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("absolute protocol path is not allowed")
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError("protocol path escapes repo root") from None
    return resolved


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


def load_protocol_text(repo_root: Path, rel_path: str) -> ProtocolBundle:
    """Load protocol text from repo_root/rel_path (UTF-8)."""
    try:
        p = _resolve_within(repo_root, rel_path)
    except ValueError as e:
        return _fallback_bundle(rel_path, error=f"protocol_path_error: {e}")
    except Exception as e:
        return _fallback_bundle(rel_path, error=f"protocol_path_error: {type(e).__name__}")
    if not p.exists() or not p.is_file():
        # Keep a minimal safe fallback if the file is missing.
        return _fallback_bundle(rel_path, error="protocol_load_error: missing_or_not_file")
    text = _read_text_limited(p, MAX_PROTOCOL_BYTES)
    if text is None:
        return _fallback_bundle(rel_path, error="protocol_load_error: unreadable_or_too_large")
    return ProtocolBundle(text=text, source_path=rel_path, loaded=True, load_error=None)
