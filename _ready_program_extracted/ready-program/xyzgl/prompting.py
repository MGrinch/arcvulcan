from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from .config import XYZGLConfig
from .protocols import load_protocol_text, should_reground
from .grounding.prompting import build_grounding

# Prompt markers (used by stub backend to extract the user text deterministically)
USER_OPEN = "<<<USER>>>"
USER_CLOSE = "<<<END_USER>>>"

PROTOCOL_OPEN = "<<<DAEDALUS_PROTOCOL>>>"
PROTOCOL_CLOSE = "<<<END_DAEDALUS_PROTOCOL>>>"

GROUNDING_OPEN = "<<<DAEDALUS_GROUNDING>>>"
GROUNDING_CLOSE = "<<<END_DAEDALUS_GROUNDING>>>"

MAX_GROUNDING_SNIPPETS = 64
MAX_GROUNDING_CHARS = 20_000
MAX_PROMPT_CHARS_HARD = 200_000

_MARKER_REPLACEMENTS = {
    USER_OPEN: "<USER_OPEN>",
    USER_CLOSE: "<USER_CLOSE>",
    PROTOCOL_OPEN: "<PROTOCOL_OPEN>",
    PROTOCOL_CLOSE: "<PROTOCOL_CLOSE>",
    GROUNDING_OPEN: "<GROUNDING_OPEN>",
    GROUNDING_CLOSE: "<GROUNDING_CLOSE>",
}
_MARKER_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(_MARKER_REPLACEMENTS, key=len, reverse=True))
)


@dataclass(frozen=True)
class PromptMeta:
    protocol_regrounded: bool
    protocol_path: str
    protocol_loaded: bool = True
    protocol_fallback: bool = False
    protocol_load_error: str | None = None
    grounding_enabled: bool = False
    grounding_meta: dict | None = None
    persona_injected: bool = False
    physics_injected: bool = False
    resonance: float | None = None
    mastery: float | None = None
    user_block_text: str = ""
    user_block_rendered: str = ""


class ProtocolFallbackRuntimeError(RuntimeError):
    """Raised when runtime regrounding would silently fall back to the minimal protocol bundle."""

    def __init__(self, reason_code: str, *, protocol_path: str) -> None:
        self.reason_code = str(reason_code or "protocol_load_error: fallback_selected")
        self.protocol_path = str(protocol_path or "")
        super().__init__(self.reason_code)


def _prompt_meta_field(meta: PromptMeta | dict, name: str, default=None):
    if isinstance(meta, dict):
        return meta.get(name, default)
    return getattr(meta, name, default)


def enforce_runtime_protocol_policy(meta: PromptMeta | dict, *, allow_fallback: bool = False) -> None:
    """Fail closed when protocol regrounding downgraded to the fallback bundle.

    Prompt construction may still annotate fallback details for tooling, but the runtime
    must not continue silently unless the caller opted into permissive fallback.
    """
    if allow_fallback:
        return
    if not bool(_prompt_meta_field(meta, "protocol_regrounded", False)):
        return
    if not bool(_prompt_meta_field(meta, "protocol_fallback", False)):
        return
    reason = str(_prompt_meta_field(meta, "protocol_load_error", "") or "protocol_load_error: fallback_selected")
    raise ProtocolFallbackRuntimeError(reason, protocol_path=str(_prompt_meta_field(meta, "protocol_path", "") or ""))


def _repo_root() -> Path:
    # xyzgl/ is one level below repo root
    return Path(__file__).resolve().parents[1]


def _resolve_within(root: Path, rel_path: str) -> Path | None:
    candidate = Path((rel_path or "").strip())
    if not str(candidate) or str(candidate) in {".", ""}:
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


def _cap_text(text: str, max_chars: int) -> str:
    t = text or ""
    if max_chars <= 0:
        return ""
    return t if len(t) <= max_chars else t[:max_chars]


def _normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", str(text or ""))


def _sanitize_prompt_block(text: str, *, max_chars: int | None = None) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    max_out: int | None = None
    pre_cap = MAX_PROMPT_CHARS_HARD
    if max_chars is not None:
        try:
            max_out = max(1, int(max_chars))
        except Exception:
            max_out = 1
        # Limit pre-normalization work to avoid oversized transient buffers.
        pre_cap = min(MAX_PROMPT_CHARS_HARD, max_out * 2)
    if len(raw) > pre_cap:
        raw = raw[:pre_cap]
    t = _normalize_nfc(raw)
    if not t:
        return ""
    if max_out is not None:
        t = _cap_text(t, max_out)
    if "<<<" not in t:
        return t
    # Prevent marker injection into structured prompt sections with a single-pass substitution.
    t = _MARKER_PATTERN.sub(lambda m: _MARKER_REPLACEMENTS[m.group(0)], t)
    return t


def normalize_and_clamp_user_text(user_text: str, *, max_chars: int) -> str:
    try:
        limit = max(1, min(int(max_chars), MAX_PROMPT_CHARS_HARD))
    except Exception:
        limit = 1
    raw = str(user_text or "")
    pre_cap = min(MAX_PROMPT_CHARS_HARD, limit * 2)
    if len(raw) > pre_cap:
        raw = raw[:pre_cap]
    normalized = _normalize_nfc(raw).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    return _cap_text(normalized, limit)


def _sanitize_user_text(user_text: str) -> str:
    t = str(user_text or "").strip()
    if not t:
        return ""
    return _sanitize_prompt_block(t)


def _extract_named_float(text: str, name: str) -> float | None:
    pattern = rf"(?:^|[\s,;]){re.escape(name)}\s*[:=]\s*(-?(?:\d+(?:\.\d*)?|\.\d+))"
    match = re.search(pattern, str(text or ""), flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def prompt_user_block_text(user_text: str, *, max_chars: int | None = None) -> str:
    """Return the sanitized learner text used inside the structured prompt."""
    raw = str(user_text or "")
    if max_chars is not None:
        raw = _cap_text(raw, _clamp_int(max_chars, low=1, high=MAX_PROMPT_CHARS_HARD))
    return _sanitize_user_text(raw)


def render_prompt_user_block(user_text: str, *, max_chars: int | None = None) -> str:
    """Return the rendered structured learner block seen by the tutor backend."""
    limit = None
    if max_chars is not None:
        try:
            limit = _clamp_int(max_chars, low=1, high=MAX_PROMPT_CHARS_HARD)
        except Exception:
            limit = 1
    body = prompt_user_block_text(user_text, max_chars=limit)
    if limit is None:
        limit = len(USER_OPEN) + len(USER_CLOSE) + len(body) + 2
    return _bounded_block(USER_OPEN, body, USER_CLOSE, max_chars=limit, allow_empty=True)


def _clamp_int(value: int, *, low: int, high: int) -> int:
    try:
        n = int(value)
    except Exception:
        n = low
    if n < low:
        return low
    if n > high:
        return high
    return n


def _join_parts_bounded(parts: list[str], *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    out: list[str] = []
    used = 0
    first = True
    for raw in parts:
        if raw is None:
            continue
        seg = str(raw)
        if not seg:
            continue
        if not first:
            if used + 2 > max_chars:
                break
            out.append("\n\n")
            used += 2
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(seg) > remaining:
            out.append(seg[:remaining])
            used += remaining
            first = False
            break
        out.append(seg)
        used += len(seg)
        first = False
    if used < max_chars:
        out.append("\n")
    return "".join(out)


def _joined_sections_len(sections: list[str]) -> int:
    items = [str(s) for s in sections if s]
    if not items:
        return 0
    return sum(len(s) for s in items) + (2 * (len(items) - 1))


def _render_sections(sections: list[str], *, max_chars: int) -> str:
    body = "\n\n".join(str(s) for s in sections if s)
    if not body:
        return ""
    if len(body) < max_chars:
        return body + "\n"
    return body


def _bounded_block(open_marker: str, text: str, close_marker: str, *, max_chars: int, allow_empty: bool) -> str:
    if max_chars <= 0:
        return ""

    fixed_empty = len(open_marker) + len(close_marker) + 1
    if max_chars < fixed_empty:
        return ""

    fixed_with_body = len(open_marker) + len(close_marker) + 2
    body = ""
    if max_chars >= fixed_with_body:
        body_budget = max_chars - fixed_with_body
        if body_budget > 0:
            body = _cap_text(text, body_budget)

    if not body and not allow_empty:
        return ""
    if body:
        return f"{open_marker}\n{body}\n{close_marker}"
    return f"{open_marker}\n{close_marker}"


def build_tutor_prompt(
    user_text: str,
    *,
    cfg: XYZGLConfig,
    turn_index: int,
    persona_text: str = "",
    physics_block: str = "",
) -> tuple[str, PromptMeta]:
    """Build the Tutor prompt with optional protocol re-grounding and curriculum grounding."""
    rr = _repo_root()
    prompt_budget = _clamp_int(getattr(cfg, "max_chars_in", 10_000), low=1, high=MAX_PROMPT_CHARS_HARD)

    effective_user_text = normalize_and_clamp_user_text(user_text, max_chars=prompt_budget)

    # Protocol re-grounding
    preg = should_reground(turn_index, cfg.protocol_reground_every)
    ptext = ""
    if preg:
        pb = load_protocol_text(rr, cfg.protocol_path)
        ptext = _sanitize_prompt_block(pb.text.strip())

    persona_clean = _sanitize_prompt_block(persona_text.strip())
    physics_clean = _sanitize_prompt_block(physics_block.strip())
    resonance = _extract_named_float(physics_clean, "resonance")
    mastery = _extract_named_float(physics_clean, "mastery")

    # Curriculum grounding
    grounding_text = ""
    grounding_meta: dict = {}
    grounding_requested = (cfg.grounding_mode or "off").lower() != "off"
    grounding_enabled = False
    if grounding_requested:
        gdir = _resolve_within(rr, cfg.grounding_dir)
        if gdir is not None:
            max_snippets = _clamp_int(cfg.grounding_max_snippets, low=0, high=MAX_GROUNDING_SNIPPETS)
            max_chars = _clamp_int(cfg.grounding_max_chars, low=0, high=MAX_GROUNDING_CHARS)
            grounding_text, grounding_meta = build_grounding(
                gdir,
                effective_user_text,
                max_snippets=max_snippets,
                max_chars=max_chars,
            )
            grounding_text = _sanitize_prompt_block(grounding_text)
            grounding_enabled = True
        else:
            grounding_meta = {"snippets": [], "grounding_dir": cfg.grounding_dir, "error": "invalid_grounding_dir"}

    # Reserve the final learner block first so optional protocol/grounding
    # content is truncated or dropped before structural markers or user text.
    sections: list[str] = [
        "You are the External Tutor for Ontario welding. Follow the ROLE PROTOCOL if provided.",
        "If grounding is provided, prefer it and cite using [src:id:ordinal].",
        "Keep answers short; ask a pointed question if reasoning is incomplete.",
    ]

    user_clean = _sanitize_user_text(effective_user_text)

    def build_user_block(current_sections: list[str]) -> str:
        budget = prompt_budget - _joined_sections_len(current_sections)
        if current_sections:
            budget -= 2
        return _bounded_block(USER_OPEN, user_clean, USER_CLOSE, max_chars=budget, allow_empty=True)

    user_block = build_user_block(sections)
    while not user_block and sections:
        sections.pop()
        user_block = build_user_block(sections)
    if not user_block:
        user_block = _bounded_block(USER_OPEN, user_clean, USER_CLOSE, max_chars=prompt_budget, allow_empty=True)

    persona_injected = False
    physics_injected = False
    optional_sections: list[tuple[str, str, str | None, str | None]] = [
        ("protocol", ptext, PROTOCOL_OPEN, PROTOCOL_CLOSE),
        ("persona", persona_clean, None, None),
        ("physics", physics_clean, None, None),
        ("grounding", grounding_text, GROUNDING_OPEN, GROUNDING_CLOSE),
    ]
    for section_name, block_text, open_marker, close_marker in optional_sections:
        if not block_text:
            continue
        current_total = _joined_sections_len(sections + [user_block])
        block_budget = prompt_budget - current_total - 2
        if block_budget <= 0:
            continue
        if open_marker is None or close_marker is None:
            block = block_text if len(block_text) <= block_budget else ""
        else:
            block = _bounded_block(open_marker, block_text, close_marker, max_chars=block_budget, allow_empty=False)
        if block:
            sections.append(block)
            if section_name == "persona":
                persona_injected = True
            elif section_name == "physics":
                physics_injected = True

    prompt = _render_sections(sections + [user_block], max_chars=prompt_budget)

    meta = PromptMeta(
        protocol_regrounded=preg,
        protocol_path=cfg.protocol_path,
        protocol_loaded=(not preg) or bool(pb.loaded),
        protocol_fallback=bool(preg and not pb.loaded),
        protocol_load_error=pb.load_error if preg else None,
        grounding_enabled=grounding_enabled,
        grounding_meta=grounding_meta,
        persona_injected=persona_injected,
        physics_injected=physics_injected,
        resonance=resonance if physics_injected else None,
        mastery=mastery if physics_injected else None,
        user_block_text=user_clean,
        user_block_rendered=user_block,
    )
    return prompt, meta
