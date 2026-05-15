from __future__ import annotations

import json
import re
import time

from .base import BackendResult, LLMBackend
from ..welding_tutor import SAFETY_PREFIX, tutor_reply

USER_OPEN = "<<<USER>>>"
USER_CLOSE = "<<<END_USER>>>"
GROUNDING_OPEN = "<<<DAEDALUS_GROUNDING>>>"
GROUNDING_CLOSE = "<<<END_DAEDALUS_GROUNDING>>>"
MAX_LEGACY_PROMPT_CHARS = 4096
_MIRROR_PAYLOAD_PREFIX = "MIRROR_CONTEXT_JSON: "
_SNIPPET_HEADER_RE = re.compile(r"^\[src:(?P<source_id>[^:\]]+):(?P<ordinal>\d+)\]\s*(?P<title>.*)$")


def _extract_field_block(text: str, field_name: str) -> str:
    prefix = f"{field_name}:"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _normalize_question_line(question: str, fallback: str) -> str:
    q = str(question or "").strip() or str(fallback or "").strip()
    if not q:
        q = "Can you explain your reasoning step by step?"
    if q.lower().startswith("question:"):
        q = q.split(":", 1)[1].strip()
    elif q.lower().startswith("q:"):
        q = q.split(":", 1)[1].strip()
    return f"Q: {q}"


def _extract_probe_question(text: str) -> str:
    marker = "keep it close to:"
    lines = text.splitlines()
    for idx, raw in enumerate(lines):
        if marker not in raw.strip().lower():
            continue
        for candidate in lines[idx + 1 :]:
            stripped = candidate.strip()
            if stripped:
                return stripped
        break
    return ""


def _extract_structured_block(prompt: str, open_marker: str, close_marker: str) -> str:
    if not prompt:
        return ""
    has_open = open_marker in prompt
    has_close = close_marker in prompt
    if not has_open and not has_close:
        return ""
    if not (has_open and has_close):
        return ""
    b = prompt.rfind(close_marker)
    if b < 0:
        return ""
    a = prompt.rfind(open_marker, 0, b)
    if a < 0:
        return ""
    a += len(open_marker)
    if a > b:
        return ""
    return prompt[a:b].strip()


def _extract_user(prompt: str) -> str:
    """Extract the user text from a structured prompt.

    Legacy prompts without explicit markers are allowed, but bounded to avoid
    prompt-size amplification in fallback mode.
    """
    if not prompt:
        return ""

    has_open = USER_OPEN in prompt
    has_close = USER_CLOSE in prompt
    if not has_open and not has_close:
        return prompt[:MAX_LEGACY_PROMPT_CHARS]
    if not (has_open and has_close):
        return ""

    # Prefer the final well-formed USER section so marker-like text in
    # protocol/grounding blocks cannot hijack extraction.
    b = prompt.rfind(USER_CLOSE)
    if b < 0:
        return ""
    a = prompt.rfind(USER_OPEN, 0, b)
    if a < 0:
        return ""
    a += len(USER_OPEN)
    if a > b:
        return ""
    return prompt[a:b].strip()


def _extract_grounding(prompt: str) -> str:
    return _extract_structured_block(prompt, GROUNDING_OPEN, GROUNDING_CLOSE)


def _extract_mirror_learner(text: str) -> str:
    """Extract learner text from structured mirror payloads.

    Mirror prompts are encoded as a single JSON payload line. Older plain-text
    delimiter parsing using ``Learner said:`` / ``Tutor replied:`` was
    injection-prone because learner content could contain those markers.
    When a structured payload marker is present but malformed, fail closed
    instead of downgrading to legacy delimiter parsing.
    """
    if not text:
        return ""

    saw_payload_marker = False
    for line in reversed(text.splitlines()):
        if not line.startswith(_MIRROR_PAYLOAD_PREFIX):
            continue
        saw_payload_marker = True
        try:
            payload = json.loads(line[len(_MIRROR_PAYLOAD_PREFIX) :].strip())
        except Exception:
            return ""
        learner = payload.get("learner") if isinstance(payload, dict) else None
        return learner.strip() if isinstance(learner, str) else ""

    if saw_payload_marker:
        return ""
    return text


def _extract_named_line(text: str, label: str) -> str:
    prefix = f"{label.lower()}:"
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if line.lower().startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _extract_teaching_block(text: str) -> str:
    lines = str(text or "").splitlines()
    body: list[str] = []
    in_block = False
    for raw in lines:
        line = raw.strip()
        low = line.lower()
        if not in_block:
            if not low.startswith("teaching block:"):
                continue
            in_block = True
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                body.append(remainder)
            continue
        if low.startswith(("question:", "q:", "topic:")):
            break
        if not line and body:
            break
        if line:
            body.append(line)
    return " ".join(body).strip()


def _strip_question_label(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if ":" in value and value.split(":", 1)[0].strip().lower() in {"q", "question"}:
        value = value.split(":", 1)[1].strip()
    return value.rstrip(" ?.")


def _seeded_choice(options: tuple[str, ...], *, seed: int | None, context: str) -> str:
    if not options:
        return ""
    key = int(seed) if seed is not None else sum(ord(ch) for ch in context)
    return options[abs(key) % len(options)]


def _mirror_core_from_context(*, topic: str, question: str, teaching: str, learner_text: str) -> str:
    haystack = " ".join(part for part in (topic, question, teaching, learner_text) if part).lower()

    if any(token in haystack for token in ("fit-up", "fitup", "root opening", "gap", "re-tack", "tack")):
        return "the fit-up or gap is probably affecting the bead shape, because uneven edges make the weld less consistent"
    if "1f" in haystack and "2f" in haystack:
        return "2F feels harder because gravity pulls on the puddle more than it does in 1F"
    if any(token in haystack for token in ("arc", "spatter", "undercut", "puddle")):
        return "arc length is probably part of it, because a long arc makes the puddle less stable"
    if any(token in haystack for token in ("distortion", "backstep", "sequence", "shrinkage")):
        return "the weld sequence probably matters, because uneven shrinkage can pull the part out of line"

    anchor = _strip_question_label(question) or topic.strip()
    if anchor:
        return f"the main point is probably tied to {anchor}"
    return "the answer probably depends on the setup, and I am still piecing it together"


def _mirror_reply_from_context(text: str, *, seed: int | None) -> str:
    learner_text = str(text or "").strip()
    topic = _extract_named_line(learner_text, "Topic")
    question = _extract_named_line(learner_text, "Question")
    teaching = _extract_teaching_block(learner_text)
    core = _mirror_core_from_context(topic=topic, question=question, teaching=teaching, learner_text=learner_text)
    opener = _seeded_choice(("I think", "My guess is", "I might be reading it as"), seed=seed, context=learner_text)
    return f"{opener} {core}. I'm not fully sure yet."


def _parse_grounding_snippets(text: str) -> list[dict[str, object]]:
    snippets: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    body: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        m = _SNIPPET_HEADER_RE.match(line.strip())
        if m:
            if current is not None:
                current["excerpt"] = "\n".join(body).strip()
                snippets.append(current)
            current = {
                "source_id": m.group("source_id").strip(),
                "ordinal": int(m.group("ordinal")),
                "title": m.group("title").strip(),
            }
            body = []
            continue
        if current is not None:
            body.append(line)
    if current is not None:
        current["excerpt"] = "\n".join(body).strip()
        snippets.append(current)
    return snippets


def _first_grounding_snippet(prompt: str) -> dict[str, object] | None:
    snippets = _parse_grounding_snippets(_extract_grounding(prompt))
    return snippets[0] if snippets else None


def _node_specific_teaching(node_id: str, node_title: str, node_summary: str) -> str:
    node = str(node_id or "").strip().lower()
    title = str(node_title or "").strip()
    summary = str(node_summary or "").strip()

    if node == "pos_1f_vs_2f" or ("1f" in title.lower() and "2f" in title.lower()):
        return (
            f"{SAFETY_PREFIX}In 1F the joint is flat, so gravity mostly helps hold the puddle in place. "
            "In 2F the joint is horizontal, so gravity tries to pull the puddle downward, which means your angle, "
            "travel control, and pause timing have to be tighter to protect the upper toe."
        )
    if node == "fitup_tacking" or "fit-up" in title.lower() or "tack" in title.lower():
        return (
            f"{SAFETY_PREFIX}Correct fit-up before welding. If the edges are uneven or the gap changes, the bead size and toes "
            "change too, so trim, grind, re-align, and place consistent tacks before you continue."
        )
    if node == "smaw_basic_arc" or "arc length" in title.lower():
        return (
            f"{SAFETY_PREFIX}Arc length controls how stable the weld feels and how the puddle behaves. "
            "If the arc gets too long, spatter and undercut tend to increase; if it gets too short, the rod can stick and the puddle becomes harder to control."
        )
    if summary:
        if not summary.startswith(SAFETY_PREFIX):
            return SAFETY_PREFIX + summary
        return summary
    anchor = title or "this step"
    return f"{SAFETY_PREFIX}Focus on {anchor} one change at a time."


def _grounded_teaching(snippet: dict[str, object]) -> str:
    source_id = str(snippet.get("source_id") or "").strip()
    ordinal = int(snippet.get("ordinal") or 0)
    cite = f"[src:{source_id}:{ordinal}]"
    if source_id == "demo_arc_control":
        return (
            f"{SAFETY_PREFIX}If fit-up is already sound and the toe still washes out, check arc length, travel speed, and work angle before blaming the joint. "
            f"A long arc tends to increase undercut and instability, so shorten the arc and hold a steadier angle. {cite}"
        )
    if source_id == "demo_fitup":
        return (
            f"{SAFETY_PREFIX}Correct fit-up first. Uneven edges or a changing root opening make the weld inconsistent, so trim, grind, re-align, and then re-tack with even spacing. {cite}"
        )
    if source_id == "demo_distortion":
        return (
            f"{SAFETY_PREFIX}Distortion control is mainly about sequence and heat distribution, not random extra tacks. "
            f"Use a balanced sequence like skip-weld or backstep so shrinkage does not pull one side first. {cite}"
        )
    excerpt = str(snippet.get("excerpt") or "").strip()
    for raw in excerpt.splitlines():
        line = raw.strip().lstrip("- ").strip()
        if line:
            return f"{SAFETY_PREFIX}{line} {cite}"
    title = str(snippet.get("title") or source_id or "the grounding note").strip()
    return f"{SAFETY_PREFIX}Use the grounded guidance from {title}. {cite}"


def _contract_tutor_reply(prompt: str) -> str | None:
    user_text = _extract_user(prompt)
    phase = _extract_field_block(user_text, "PHASE").upper()
    if phase not in {"TEACH", "PROBE"}:
        return None

    node_id = _extract_field_block(user_text, "NODE_ID")
    node_title = _extract_field_block(user_text, "NODE_TITLE") or "this step"
    node_summary = _extract_field_block(user_text, "NODE_SUMMARY")
    grounding_snippet = _first_grounding_snippet(prompt)
    teaching = _grounded_teaching(grounding_snippet) if grounding_snippet else _node_specific_teaching(node_id, node_title, node_summary)

    if phase == "TEACH":
        question = _normalize_question_line(
            "",
            f"In your own words, what is the key point of {node_title}?",
        )
        return f"{teaching}\n{question}"

    pointed_question = _extract_probe_question(user_text)
    hint = teaching
    question = _normalize_question_line(
        pointed_question,
        f"What is the missing step for {node_title}?",
    )
    return f"{hint}\n{question}"


class StubTutorBackend(LLMBackend):
    """Deterministic placeholder tutor.

    Used by harnesses and as a safe fallback when real credentials are absent.
    """

    name = "stub"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        t0 = time.monotonic()
        text = _contract_tutor_reply(prompt)
        if text is None:
            user_text = _extract_user(prompt)
            text = tutor_reply(user_text, seed=seed)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return BackendResult(text=text, backend=self.name, model="stub", latency_ms=latency_ms)


class StubMirrorBackend(LLMBackend):
    """Deterministic mirror that predicts a plausible learner response.

    The stub mirror must stay learner-shaped: tentative, first-person, and
    non-imperative.
    """

    name = "mirror_stub"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        t0 = time.monotonic()
        text_in = _extract_mirror_learner(_extract_user(prompt))
        text = _mirror_reply_from_context(text_in, seed=seed)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return BackendResult(text=text, backend=self.name, model="stub", latency_ms=latency_ms)
