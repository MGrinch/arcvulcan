from __future__ import annotations

from dataclasses import dataclass
import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")
MAX_POLICY_INPUT_CHARS = 20_000
MAX_POLICY_TOKENS = 10_000
_EXPLANATION_CONNECTORS = {
    "because",
    "so",
    "means",
    "affects",
    "changes",
    "causes",
    "keeps",
    "makes",
    "controls",
    "lets",
    "requires",
    "prevents",
    "helps",
    "therefore",
    "since",
    "while",
    "when",
}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "how", "i",
    "if", "in", "into", "is", "it", "its", "of", "on", "or", "our", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "to", "up", "we", "what", "when",
    "where", "which", "why", "with", "you", "your", "than", "too", "very", "can", "could",
    "should", "would", "do", "does", "did", "have", "has", "had", "will", "just", "also",
}
_GENERIC_FILLER = {"thing", "things", "stuff", "something", "anything", "everything", "need", "needs", "good", "bad", "okay", "ok"}


@dataclass(frozen=True)
class TeachingBudget:
    """How much material to present this turn."""

    min_sentences: int
    max_sentences: int
    density: str  # "dense" | "light"


def infer_user_state(user_text: str, *, typing_ms: int | None = None) -> str:
    """Infer a coarse learner state.

    Current contract (deterministic, intentionally simple):
      - "frustrated" if the user text is very short, contains "idk", or is a question-only
      - otherwise "flow"

    This is a placeholder sensor; replace later with a trained classifier under
    the Witness Protocol (repro-first).
    """
    raw = str(user_text or "")
    if len(raw) > MAX_POLICY_INPUT_CHARS:
        raw = raw[:MAX_POLICY_INPUT_CHARS]
    t = raw.strip().lower()
    if not t:
        return "frustrated"
    if "idk" in t or "i don't know" in t or "dont know" in t:
        return "frustrated"
    if len(t) < 50:
        return "frustrated"
    if t.endswith("?") and len(t.split()) <= 8:
        return "frustrated"
    # Optional typing signal: slow + short tends to be frustration.
    if typing_ms is not None and typing_ms > 12_000 and len(t) < 120:
        return "frustrated"
    return "flow"


def teaching_budget(state: str) -> TeachingBudget:
    """Map state -> budget.

    NORTH STAR rule:
      - FLOW: 10–15 dense sentences
      - FRUSTRATED: 7–10 light sentences
    """
    s = (state or "").strip().lower()
    if s == "frustrated":
        return TeachingBudget(min_sentences=7, max_sentences=10, density="light")
    return TeachingBudget(min_sentences=10, max_sentences=15, density="dense")


def _required_token_set(required_keywords: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw in required_keywords:
        for token in _TOKEN_RE.findall(raw):
            if token:
                tokens.add(token)
    return tokens


def _longest_required_run(answer_tokens: list[str], required_tokens: set[str]) -> int:
    longest = 0
    current = 0
    for token in answer_tokens:
        if token in required_tokens:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _explanation_quality_audit(required_keywords: list[str], answer_tokens: list[str]) -> dict:
    required_tokens = _required_token_set(required_keywords)
    content_tokens = [
        token
        for token in answer_tokens
        if token not in required_tokens and token not in _STOPWORDS and token not in _GENERIC_FILLER and len(token) >= 3
    ]
    distinct_content_tokens = sorted(set(content_tokens))
    min_content_tokens = max(2, min(4, len(required_tokens) or 1))
    has_connector = any(token in _EXPLANATION_CONNECTORS for token in answer_tokens)
    longest_required_run = _longest_required_run(answer_tokens, required_tokens)

    reasons: list[str] = []
    if len(distinct_content_tokens) < min_content_tokens:
        reasons.append("insufficient_explanatory_content")
    if not has_connector and len(distinct_content_tokens) < (min_content_tokens + 1):
        reasons.append("missing_explanatory_link")
    if longest_required_run >= max(3, len(required_tokens)) and len(distinct_content_tokens) < (min_content_tokens + 1):
        reasons.append("keyword_stuffing_pattern")

    return {
        "quality_passed": not reasons,
        "quality_reasons": reasons,
        "content_tokens": distinct_content_tokens[:32],
        "content_token_count": len(distinct_content_tokens),
        "min_content_tokens": min_content_tokens,
        "has_connector": has_connector,
        "longest_required_run": longest_required_run,
    }


def required_keywords_audit(required: list[str], user_answer: str) -> dict:
    """Return deterministic closure evidence for auditing artifacts.

    Keyword coverage remains necessary, but node closure now also requires
    a small amount of explanatory structure so pure keyword stuffing cannot
    unlock mastery progression.
    """
    ans = str(user_answer or "")
    if len(ans) > MAX_POLICY_INPUT_CHARS:
        ans = ans[:MAX_POLICY_INPUT_CHARS]
    ans = ans.lower()
    ans_words = _TOKEN_RE.findall(ans)
    if len(ans_words) > MAX_POLICY_TOKENS:
        ans_words = ans_words[:MAX_POLICY_TOKENS]
    ans_tokens = set(ans_words)
    ans_norm = " ".join(ans_words)
    req = [str(r).strip().lower() for r in (required or []) if str(r).strip()]
    if len(req) > 512:
        req = req[:512]

    matched: list[str] = []
    missing: list[str] = []
    for r in req:
        parts = _TOKEN_RE.findall(r)
        if not parts:
            missing.append(r)
            continue
        normalized = " ".join(parts)
        if len(parts) == 1:
            ok = parts[0] in ans_tokens
        else:
            ok = normalized in ans_norm
        if ok:
            matched.append(normalized)
        else:
            missing.append(normalized)

    quality = _explanation_quality_audit(req, ans_words)
    return {
        "required_keywords": req,
        "matched_keywords": matched,
        "missing_keywords": missing,
        **quality,
        "satisfied": bool(req) and not missing and bool(quality["quality_passed"]),
    }


def required_keywords_satisfied(required: list[str], user_answer: str) -> bool:
    """Deterministic closure heuristic.

    Closure still requires keyword coverage, but now also demands a minimum
    amount of explanatory content so bare token stuffing cannot advance a node.
    """
    return bool(required_keywords_audit(required, user_answer)["satisfied"])
