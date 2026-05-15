from __future__ import annotations

import hashlib
import json

from ..backends.registry import BackendConfigError, get_mirror_backend, require_real_backends
from ..config import XYZGLConfig
from ..router import sanitize_runtime_backend_error, validate_runtime_backend_result_meta, validate_runtime_backend_result_shape
from .parsing import safe_backend_error


_MIRROR_CONTEXT_CHARS = 2_000
_MIRROR_PAYLOAD_PREFIX = "MIRROR_CONTEXT_JSON: "


def _clamp(s: str, n: int) -> str:
    if n <= 0:
        return ""
    return s if len(s) <= n else s[:n]


def _has_nonempty_backend_text(text: str) -> bool:
    return bool(str(text or "").strip())


def _stable_digest(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def _mirror_prompt_mode(cfg: XYZGLConfig) -> str:
    return "sanitized" if bool(getattr(cfg, "mirror_send_user_content", False)) else "redacted"


def _mirror_context_block(text: str, *, send_raw: bool, label: str) -> str:
    cleaned = _clamp(str(text or "").strip(), _MIRROR_CONTEXT_CHARS)
    if send_raw:
        return cleaned
    return f"<redacted:{label}> len={len(text or '')} digest={_stable_digest(text or '')}"


def _build_mirror_prompt(*, learner_ctx: str, tutor_ctx: str) -> str:
    payload = json.dumps({"learner": learner_ctx, "tutor": tutor_ctx}, ensure_ascii=False, separators=(",", ":"))
    return (
        "You are simulating the learner (Ontario welding student).\n"
        f"{_MIRROR_PAYLOAD_PREFIX}{payload}\n"
        "Predict the learner's next reply in 1-3 sentences."
    )


def run_mirror_prediction(
    *,
    cfg: XYZGLConfig,
    seed: int | None,
    node_title: str,
    teaching_block: str,
    question: str,
) -> tuple[str | None, dict | None]:
    """Optional: simulate the learner's answer using the local Mirror backend."""
    if not cfg.enable_mirror:
        return None, None

    prompt_mode = _mirror_prompt_mode(cfg)
    send_raw = prompt_mode == "sanitized"

    try:
        mirror = get_mirror_backend(cfg)
    except BackendConfigError as e:
        if require_real_backends():
            raise
        return None, {"error": sanitize_runtime_backend_error(f"mirror_backend_config_error: {e}", backend_error_limit=cfg.max_chars_out), "prompt_mode": prompt_mode}

    max_in = int(cfg.max_chars_in) if int(cfg.max_chars_in) > 0 else 10_000
    safe_title = _clamp(str(node_title or ""), 200)
    safe_teaching = _clamp(str(teaching_block or ""), max_in)
    safe_question = _clamp(str(question or ""), min(max_in, 2_000))
    learner_ctx = _mirror_context_block(
        f"Topic: {safe_title}\nTeaching block:\n{safe_teaching}\n\nQuestion: {safe_question}",
        send_raw=send_raw,
        label="session-turn",
    )
    tutor_ctx = _mirror_context_block(
        f"Topic: {safe_title}\nQuestion: {safe_question}",
        send_raw=send_raw,
        label="session-question",
    )
    mprompt = _build_mirror_prompt(learner_ctx=learner_ctx, tutor_ctx=tutor_ctx)

    try:
        res = mirror.generate(mprompt, seed=seed)
        shape_error = validate_runtime_backend_result_shape(res, role="mirror_backend")
        if shape_error:
            if require_real_backends():
                raise RuntimeError(shape_error)
            return None, {"error": sanitize_runtime_backend_error(shape_error, backend_error_limit=cfg.max_chars_out), "prompt_mode": prompt_mode}
        meta_error = validate_runtime_backend_result_meta(res, role="mirror_backend")
        if meta_error:
            if require_real_backends():
                raise RuntimeError(meta_error)
            return None, {"error": sanitize_runtime_backend_error(meta_error, backend_error_limit=cfg.max_chars_out), "prompt_mode": prompt_mode}
        if not _has_nonempty_backend_text(res.text):
            contract_error = "mirror_backend_contract_error: empty_reply"
            if require_real_backends():
                raise RuntimeError(contract_error)
            return None, {"error": sanitize_runtime_backend_error(contract_error, backend_error_limit=cfg.max_chars_out), "prompt_mode": prompt_mode}
        return res.text, {"backend": res.backend, "model": res.model, "latency_ms": res.latency_ms, "prompt_mode": prompt_mode}
    except Exception as e:
        if require_real_backends():
            raise
        return None, {"error": sanitize_runtime_backend_error(f"mirror_backend_error: {safe_backend_error(e)}", backend_error_limit=cfg.max_chars_out), "prompt_mode": prompt_mode}
