from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable


SideEffectMeta = dict[str, Any]


def side_effect_meta(stdout_text: str, stderr_text: str) -> SideEffectMeta:
    stdout_text = "" if stdout_text is None else str(stdout_text)
    stderr_text = "" if stderr_text is None else str(stderr_text)
    stdout_present = bool(stdout_text)
    stderr_present = bool(stderr_text)
    return {
        "stdout_present": stdout_present,
        "stdout_len": len(stdout_text),
        "stderr_present": stderr_present,
        "stderr_len": len(stderr_text),
        "channel_count": int(stdout_present) + int(stderr_present),
        "total_len": len(stdout_text) + len(stderr_text),
    }


def empty_side_effect_meta() -> SideEffectMeta:
    return side_effect_meta("", "")


def capture_callable(fn: Callable[..., Any], /, *args, **kwargs):
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            result = fn(*args, **kwargs)
    except Exception as e:
        return False, e, side_effect_meta(stdout_buf.getvalue(), stderr_buf.getvalue())
    return True, result, side_effect_meta(stdout_buf.getvalue(), stderr_buf.getvalue())


def has_side_effects(meta: SideEffectMeta) -> bool:
    return bool(meta.get("stdout_present") or meta.get("stderr_present"))


def side_effect_reason(meta: SideEffectMeta, *, stage: str) -> str:
    if not has_side_effects(meta):
        return ""
    parts: list[str] = []
    if meta.get("stdout_present"):
        parts.append(f"stdout={int(meta.get('stdout_len', 0))}")
    if meta.get("stderr_present"):
        parts.append(f"stderr={int(meta.get('stderr_len', 0))}")
    detail = ", ".join(parts) if parts else "captured"
    return f"unexpected stdout/stderr side effects during {stage} ({detail})"


def record_side_effect_failure(out: dict[str, Any], meta: SideEffectMeta, *, stage: str) -> bool:
    if not has_side_effects(meta):
        return False
    reason = side_effect_reason(meta, stage=stage)
    out["status"] = "FAIL"
    out["error"] = reason
    out["side_effect_stage"] = stage
    out["side_effects"] = meta
    reasons = list(out.get("verdict_reasons") or [])
    reasons.append(reason)
    out["verdict_reasons"] = reasons
    return True
