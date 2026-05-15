from __future__ import annotations

import json
import re

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def _contains_surrogate(value: object) -> bool:
    if isinstance(value, str):
        return bool(_SURROGATE_RE.search(value))
    if isinstance(value, list):
        return any(_contains_surrogate(x) for x in value)
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and _SURROGATE_RE.search(k):
                return True
            if _contains_surrogate(v):
                return True
    return False


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate JSON key: {k}")
        out[k] = v
    return out


def _loads_json_eval(raw: str) -> dict:
    obj = json.loads(raw, object_pairs_hook=_no_duplicate_pairs)
    if not isinstance(obj, dict):
        raise ValueError("eval json must be an object")
    if _contains_surrogate(obj):
        raise ValueError("eval json contains invalid surrogate code points")
    return obj


def safe_backend_error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def _iter_lines_stream(text: str):
    s = str(text or "")
    if not s:
        return
    # Stream-style line parsing avoids splitlines() list materialization on large payloads.
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    start = 0
    while True:
        idx = s.find("\n", start)
        if idx < 0:
            yield s[start:]
            break
        yield s[start:idx]
        start = idx + 1


def parse_question(text: str) -> tuple[str, str]:
    """Split tutor output into (teaching, question).

    Convention: tutor includes a line starting with 'Q:' or 'Question:'.
    If absent, return the full text as teaching and a generic question.
    """
    if not text:
        return "", "Q: Can you explain your reasoning step by step?"

    teaching_lines: list[str] = []
    q_line = None
    for raw in _iter_lines_stream(text):
        ln = raw.rstrip()
        low = ln.strip().lower()
        if low.startswith("q:") or low.startswith("question:"):
            q_line = ln.strip()
            break
        teaching_lines.append(ln)

    if q_line is None:
        return text.strip(), "Q: Can you explain your reasoning step by step?"

    teaching = "\n".join(teaching_lines).strip()
    q = q_line
    if q.lower().startswith("question:"):
        q = "Q: " + q[len("question:") :].strip()
    if not q.lower().startswith("q:"):
        q = "Q: " + q
    return teaching, q


def parse_eval_block(text: str) -> dict:
    """Parse an evaluation block produced by the Tutor.

    Preferred format (LLM-agnostic):
      EVAL: ...
      GAPS: ...
      NEXT_ACTION: PROBE|CLOSE_NODE
      Q2: ... (if PROBE)

    If parsing fails, returns a conservative default.
    """
    raw = (text or "").strip()
    out = {
        "evaluation": raw,
        "gaps": "",
        "next_action": "PROBE",
        "next_question": "Q2: What's the missing step in your reasoning?",
    }
    if not raw:
        return out

    # Try JSON first (future-proof).
    if raw.startswith("{") and raw.endswith("}"):
        try:
            j = _loads_json_eval(raw)
            na = str(j.get("next_action") or "PROBE").strip().upper()
            out["evaluation"] = str(j.get("evaluation") or raw)
            out["gaps"] = str(j.get("gaps") or "")
            out["next_action"] = na if na in {"PROBE", "CLOSE_NODE"} else "PROBE"
            out["next_question"] = str(j.get("next_question") or out["next_question"])
            return out
        except Exception:
            pass

    # Line-based parse.
    for line in _iter_lines_stream(raw):
        ln = line.strip()
        if not ln:
            continue
        low = ln.lower()
        if low.startswith("eval:"):
            out["evaluation"] = ln.split(":", 1)[1].strip()
        elif low.startswith("gaps:"):
            out["gaps"] = ln.split(":", 1)[1].strip()
        elif low.startswith("next_action:"):
            na = ln.split(":", 1)[1].strip().upper()
            if na in {"PROBE", "CLOSE_NODE"}:
                out["next_action"] = na
        elif low.startswith("q2:") or low.startswith("probe:"):
            out["next_question"] = "Q2: " + ln.split(":", 1)[1].strip()

    return out
