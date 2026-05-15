from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .backends.registry import BackendConfigError, get_mirror_backend, get_tutor_backend, require_real_backends
from .config import MIN_SAFE_REPLY_CHARS, XYZGLConfig
from .prompting import build_tutor_prompt, enforce_runtime_protocol_policy, normalize_and_clamp_user_text
from .welding_tutor import SAFETY_PREFIX

_MIRROR_CONTEXT_CHARS = 512
_MIRROR_SEND_USER_CONTENT_ENV = "DAEDALUS_MIRROR_SEND_USER_CONTENT"
_EXPOSE_BACKEND_ERRORS_ENV = "DAEDALUS_EXPOSE_BACKEND_ERRORS"
_MAX_IO_CHARS_HARD = 200_000
_MIRROR_PAYLOAD_PREFIX = "MIRROR_CONTEXT_JSON: "
_QUERY_SECRET_RE = re.compile(
    r"([?&](?:token|api_key|apikey|key|auth|authorization)=)[^&#]+",
    flags=re.IGNORECASE,
)
_HEADER_SECRET_RE = re.compile(
    r"(?im)\b(authorization|cookie|set-cookie|x-api-key|x-goog-api-key)\s*:\s*[^\r\n]+"
)
_GENERIC_SECRET_RE = re.compile(
    r"\b(?:AIza[0-9A-Za-z\-_]{20,}|sk-[0-9A-Za-z]{20,}|AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{20,})\b"
)
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "private_key",
    "bearer",
)


def _clamp(s: str, n: int) -> str:
    if n <= 0:
        return ""
    return s if len(s) <= n else s[:n]


def _bounded_limit(value: int | None, *, default: int, hard_max: int = _MAX_IO_CHARS_HARD) -> int:
    try:
        iv = int(value if value is not None else default)
    except Exception:
        iv = default
    if iv < 1:
        return 1
    return min(iv, hard_max)


def _stable_digest(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def _sanitize_path_like(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    p = Path(raw)
    if p.is_absolute():
        tail = p.name or "<root>"
        return f"<abs>/{tail}"
    return raw.replace("\\", "/")


def _redact_url_credentials(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    try:
        sp = urlsplit(raw)
    except Exception:
        return _QUERY_SECRET_RE.sub(r"\1<redacted>", raw)
    netloc = sp.netloc
    if "@" in netloc:
        _, host = netloc.rsplit("@", 1)
        netloc = f"***@{host}"
    out = urlunsplit(SplitResult(sp.scheme, netloc, sp.path, sp.query, sp.fragment))
    return _QUERY_SECRET_RE.sub(r"\1<redacted>", out)


def _sanitize_text(text: str, *, limit: int) -> str:
    t = _clamp((text or "").strip(), limit)
    t = _GENERIC_SECRET_RE.sub("<redacted>", t)
    t = _QUERY_SECRET_RE.sub(r"\1<redacted>", t)
    t = _HEADER_SECRET_RE.sub(lambda m: f"{m.group(1)}: <redacted>", t)
    return t


def _is_sensitive_key_name(key: str) -> bool:
    k = str(key or "").strip().lower().replace("-", "_")
    if not k:
        return False
    return any(part in k for part in _SENSITIVE_KEY_PARTS)


def _normalize_input_text(text: str) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    return t.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_input_text_bounded(text: str, *, max_chars: int) -> str:
    raw = str(text or "")
    pre_cap = min(_MAX_IO_CHARS_HARD, max(1, int(max_chars)) * 2)
    if len(raw) > pre_cap:
        raw = raw[:pre_cap]
    return _normalize_input_text(raw)


def _sanitize_obj(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = str(k)
            if _is_sensitive_key_name(key):
                out[key] = "<redacted>"
                continue
            out[key] = _sanitize_obj(v)
            if isinstance(out[key], str):
                low = key.lower()
                if low.endswith("_path") or low.endswith("_dir") or low == "path":
                    out[key] = _sanitize_path_like(out[key])
                elif low.endswith("_host") or low.endswith("_url") or low in {"host", "url"}:
                    out[key] = _redact_url_credentials(out[key])
        return out
    if isinstance(value, list):
        return [_sanitize_obj(v) for v in value]
    if isinstance(value, str):
        return _sanitize_text(value, limit=1024)
    return value


def _meta_field(meta, name: str, default=None):
    if isinstance(meta, dict):
        return meta.get(name, default)
    return getattr(meta, name, default)


def sanitize_runtime_backend_error(value: str | None, *, backend_error_limit: int | None = None) -> str | None:
    if not value:
        return None
    limit = _bounded_limit(backend_error_limit, default=1024)
    return _sanitize_text(str(value), limit=limit)


def sanitize_prompt_meta(
    meta,
    *,
    grounding=None,
    tutor_backend=None,
    tutor_model=None,
    tutor_latency_ms=None,
    phase: str | None = None,
    backend_error: str | None = None,
    backend_error_limit: int | None = None,
) -> dict:
    out = {
        "protocol_regrounded": _meta_field(meta, "protocol_regrounded", False),
        "protocol_path": _sanitize_path_like(str(_meta_field(meta, "protocol_path", "") or "")),
        "protocol_loaded": bool(_meta_field(meta, "protocol_loaded", True)),
        "protocol_fallback": bool(_meta_field(meta, "protocol_fallback", False)),
        "grounding_enabled": _meta_field(meta, "grounding_enabled", False),
        "grounding": _sanitize_obj(
            grounding if grounding is not None else _meta_field(meta, "grounding", _meta_field(meta, "grounding_meta", {}))
        ),
    }

    protocol_load_error = _meta_field(meta, "protocol_load_error", None)
    if protocol_load_error:
        out["protocol_load_error"] = _sanitize_text(str(protocol_load_error), limit=256)

    resolved_phase = phase if phase is not None else _meta_field(meta, "phase", None)
    if resolved_phase:
        out["phase"] = _sanitize_text(str(resolved_phase), limit=64)

    resolved_backend = tutor_backend if tutor_backend is not None else _meta_field(meta, "tutor_backend", None)
    if resolved_backend is not None:
        out["tutor_backend"] = _sanitize_text(str(resolved_backend), limit=256)

    resolved_model = tutor_model if tutor_model is not None else _meta_field(meta, "tutor_model", None)
    if resolved_model is not None:
        out["tutor_model"] = _sanitize_text(str(resolved_model), limit=256)

    resolved_latency = tutor_latency_ms if tutor_latency_ms is not None else _meta_field(meta, "tutor_latency_ms", None)
    if resolved_latency is not None:
        out["tutor_latency_ms"] = resolved_latency

    user_block_text = _meta_field(meta, "user_block_text", None)
    if user_block_text not in (None, ""):
        out["user_block_text"] = _sanitize_text(str(user_block_text), limit=_bounded_limit(None, default=10_000))

    user_block_rendered = _meta_field(meta, "user_block_rendered", None)
    if user_block_rendered not in (None, ""):
        out["user_block_rendered"] = _sanitize_text(str(user_block_rendered), limit=_bounded_limit(None, default=10_000))

    resolved_backend_error = backend_error if backend_error is not None else _meta_field(meta, "backend_error", None)
    sanitized_error = sanitize_runtime_backend_error(resolved_backend_error, backend_error_limit=backend_error_limit)
    if sanitized_error:
        out["backend_error"] = sanitized_error if _expose_backend_errors() else "backend_error_redacted"

    return out


def _mirror_send_user_content() -> bool:
    v = os.getenv(_MIRROR_SEND_USER_CONTENT_ENV, "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _expose_backend_errors() -> bool:
    v = os.getenv(_EXPOSE_BACKEND_ERRORS_ENV, "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _mirror_context_block(text: str, *, send_raw: bool, label: str) -> str:
    cleaned = _sanitize_text(text, limit=_MIRROR_CONTEXT_CHARS)
    if send_raw:
        return cleaned
    return f"<redacted:{label}> len={len(text or '')} digest={_stable_digest(text or '')}"


def _format_tutor_reply(text: str, *, limit: int) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if raw.startswith(SAFETY_PREFIX):
        body = raw[len(SAFETY_PREFIX):].strip()
        normalized = raw
    else:
        body = raw
        normalized = SAFETY_PREFIX + raw
    if not body:
        return ""
    try:
        bounded_limit = max(MIN_SAFE_REPLY_CHARS, int(limit))
    except Exception:
        bounded_limit = MIN_SAFE_REPLY_CHARS
    return _clamp(normalized, bounded_limit)


def _has_nonempty_backend_text(text: str) -> bool:
    return bool(str(text or "").strip())


def validate_runtime_backend_result_shape(res, *, role: str = "backend") -> str | None:
    if res is None:
        return f"{role}_contract_error: missing_result"
    for field in ("text", "backend", "model", "latency_ms"):
        try:
            getattr(res, field)
        except Exception as e:
            return f"{role}_contract_error: missing_field:{field}:{e.__class__.__name__}"
    return None


def validate_runtime_backend_result_meta(res, *, role: str = "backend") -> str | None:
    backend = getattr(res, "backend", None)
    if not isinstance(backend, str) or not backend:
        return f"{role}_contract_error: invalid_backend"

    model = getattr(res, "model", None)
    if not isinstance(model, str) or not model:
        return f"{role}_contract_error: invalid_model"

    latency_ms = getattr(res, "latency_ms", None)
    if isinstance(latency_ms, bool) or not isinstance(latency_ms, int) or latency_ms < 0:
        return f"{role}_contract_error: invalid_latency_ms"

    return None


def _append_backend_error(current: str | None, message: str) -> str:
    return (current + " | " if current else "") + message



def _compute_single_turn_physics(text_in: str, *, cfg: XYZGLConfig) -> dict[str, float] | None:
    """Compute deterministic single-turn physics when lithosphere support is enabled."""
    if not bool(getattr(cfg, "lithosphere_enabled", False)):
        return None

    from .knowledge.embeddings import text_to_vector
    from .knowledge.lithosphere import Lithosphere

    embed_dim = int(getattr(cfg, "lithosphere_embed_dim", 768))
    grains = int(getattr(cfg, "lithosphere_grains", 8))
    lithosphere_seed = getattr(cfg, "lithosphere_seed", None)

    litho = Lithosphere(embed_dim=embed_dim, grains=grains, seed=lithosphere_seed)
    vec = text_to_vector(text_in, dim=embed_dim)
    node_id = "single_turn"
    litho.get_or_create(node_id, vec, text_in)
    resonance = litho.compute_resonance(node_id, vec)

    return {
        "mastery": round(float(litho.get_mastery(node_id)), 4),
        "resonance": round(float(resonance), 4),
        "text_similarity": 1.0,
        "mastery_delta": 0.0,
    }


def _build_single_turn_persona_instruction(
    *,
    cfg: XYZGLConfig,
    physics: dict[str, float] | None,
) -> str:
    """Build a persona instruction block for single-turn routing when enabled."""
    if not bool(getattr(cfg, "persona_enabled", False)):
        return ""

    from .persona import build_persona_instruction, persona_from_config

    persona_cfg = persona_from_config(cfg)
    if persona_cfg is None:
        return ""

    mastery = float((physics or {}).get("mastery", 0.0))
    resonance = float((physics or {}).get("resonance", 0.0))
    instruction = build_persona_instruction(persona_cfg, mastery=mastery, resonance=resonance)
    return str(instruction or "")


def _build_tutor_prompt_for_route_turn(
    user_text: str,
    *,
    cfg: XYZGLConfig,
    turn_index: int,
    persona_text: str = "",
):
    """Build the tutor prompt, injecting persona text when the prompt builder supports it."""
    prompt_kwargs = {"cfg": cfg, "turn_index": turn_index}
    prompt_sig = inspect.signature(build_tutor_prompt)
    if persona_text and "persona_text" in prompt_sig.parameters:
        return build_tutor_prompt(user_text, persona_text=persona_text, **prompt_kwargs)
    return build_tutor_prompt(user_text, **prompt_kwargs)


def _build_mirror_prompt(*, learner_ctx: str, tutor_ctx: str) -> str:
    payload = json.dumps({"learner": learner_ctx, "tutor": tutor_ctx}, ensure_ascii=False, separators=(",", ":"))
    return (
        "You are simulating the learner (Ontario welding student).\n"
        f"{_MIRROR_PAYLOAD_PREFIX}{payload}\n"
        "Predict the learner's next reply in 1-3 sentences."
    )


def route_turn(
    user_text: str,
    *,
    seed: int | None = None,
    cfg: XYZGLConfig | None = None,
    turn_index: int = 0,
) -> dict:
    """Route a single user turn.

    Behavior:
      - Tutor backend generates the primary reply
      - Optional Mirror backend predicts the learner's next reply (simulation)
      - Protocol and grounding are injected into Tutor prompts when configured

    Determinism:
      - Harnesses default to cfg.tutor_backend='stub'
      - Real backends are only used when explicitly enabled by env/CLI
    """

    cfg = cfg or XYZGLConfig.from_env()
    strict_tutor = require_real_backends()

    in_limit = _bounded_limit(getattr(cfg, "max_chars_in", None), default=10_000)
    out_limit = _bounded_limit(getattr(cfg, "max_chars_out", None), default=10_000)
    text_in = normalize_and_clamp_user_text(user_text, max_chars=in_limit)

    backend_error: str | None = None
    physics = _compute_single_turn_physics(text_in, cfg=cfg)
    persona_instruction = _build_single_turn_persona_instruction(cfg=cfg, physics=physics)

    # Build structured Tutor prompt (protocol + grounding + user section)
    tutor_prompt, prompt_meta = _build_tutor_prompt_for_route_turn(
        text_in,
        cfg=cfg,
        turn_index=turn_index,
        persona_text=persona_instruction,
    )
    enforce_runtime_protocol_policy(prompt_meta, allow_fallback=bool(getattr(cfg, "allow_protocol_fallback", False)))

    # Tutor
    try:
        tutor = get_tutor_backend(cfg)
    except BackendConfigError as e:
        if strict_tutor:
            raise
        tutor = get_tutor_backend(XYZGLConfig())
        backend_error = f"tutor_backend_config_error: {e}"

    try:
        tutor_res = tutor.generate(tutor_prompt, seed=seed)
    except Exception as e:
        # Mirror path already tolerates backend errors unless strict mode is enabled.
        # Tutor should do the same so a single backend hiccup doesn't crash the session.
        if strict_tutor:
            raise
        backend_error = _append_backend_error(backend_error, f"tutor_backend_error: {e}")
        tutor = get_tutor_backend(XYZGLConfig())  # deterministic stub fallback
        tutor_res = tutor.generate(tutor_prompt, seed=seed)

    shape_error = validate_runtime_backend_result_shape(tutor_res, role="tutor_backend")
    if shape_error:
        if strict_tutor:
            raise RuntimeError(shape_error)
        backend_error = _append_backend_error(backend_error, shape_error)
        tutor = get_tutor_backend(XYZGLConfig())
        tutor_res = tutor.generate(tutor_prompt, seed=seed)
        shape_error = validate_runtime_backend_result_shape(tutor_res, role="tutor_backend")
        if shape_error:
            raise RuntimeError(f"stub {shape_error}")

    meta_error = validate_runtime_backend_result_meta(tutor_res, role="tutor_backend")
    if meta_error:
        if strict_tutor:
            raise RuntimeError(meta_error)
        backend_error = _append_backend_error(backend_error, meta_error)
        tutor = get_tutor_backend(XYZGLConfig())
        tutor_res = tutor.generate(tutor_prompt, seed=seed)
        shape_error = validate_runtime_backend_result_shape(tutor_res, role="tutor_backend")
        if shape_error:
            raise RuntimeError(f"stub {shape_error}")
        meta_error = validate_runtime_backend_result_meta(tutor_res, role="tutor_backend")
        if meta_error:
            raise RuntimeError(f"stub {meta_error}")

    reply = _format_tutor_reply(tutor_res.text, limit=out_limit)
    if not reply:
        contract_error = "tutor_backend_contract_error: empty_reply"
        if strict_tutor:
            raise RuntimeError(contract_error)
        backend_error = _append_backend_error(backend_error, contract_error)
        tutor = get_tutor_backend(XYZGLConfig())
        tutor_res = tutor.generate(tutor_prompt, seed=seed)
        reply = _format_tutor_reply(tutor_res.text, limit=out_limit)
        if not reply:
            raise RuntimeError("stub tutor backend produced empty contract reply")


    # Mirror (optional)
    mirror_prediction = None
    mirror_meta = None
    if cfg.enable_mirror:
        try:
            mirror = get_mirror_backend(cfg)
            send_raw_mirror = _mirror_send_user_content()
            learner_ctx = _mirror_context_block(text_in, send_raw=send_raw_mirror, label="learner")
            tutor_ctx = _mirror_context_block(reply, send_raw=send_raw_mirror, label="tutor")
            mprompt = _build_mirror_prompt(learner_ctx=learner_ctx, tutor_ctx=tutor_ctx)
            mres = mirror.generate(mprompt, seed=seed)
            shape_error = validate_runtime_backend_result_shape(mres, role="mirror_backend")
            if shape_error:
                if require_real_backends():
                    raise RuntimeError(shape_error)
                backend_error = _append_backend_error(backend_error, shape_error)
            else:
                meta_error = validate_runtime_backend_result_meta(mres, role="mirror_backend")
                if meta_error:
                    if require_real_backends():
                        raise RuntimeError(meta_error)
                    backend_error = _append_backend_error(backend_error, meta_error)
                elif not _has_nonempty_backend_text(mres.text):
                    contract_error = "mirror_backend_contract_error: empty_reply"
                    if require_real_backends():
                        raise RuntimeError(contract_error)
                    backend_error = _append_backend_error(backend_error, contract_error)
                else:
                    mirror_prediction = _clamp(mres.text, out_limit)
                    mirror_meta = {
                        "backend": mres.backend,
                        "model": mres.model,
                        "latency_ms": mres.latency_ms,
                        # send_raw currently means bounded full-text mirror context, but still sanitized.
                        "prompt_mode": "sanitized" if send_raw_mirror else "redacted",
                    }
        except BackendConfigError as e:
            if require_real_backends():
                raise
            backend_error = _append_backend_error(backend_error, f"mirror_backend_config_error: {e}")
        except Exception as e:
            if require_real_backends():
                raise
            backend_error = _append_backend_error(backend_error, f"mirror_backend_error: {e}")

    sanitized_prompt_meta = sanitize_prompt_meta(prompt_meta, backend_error=backend_error, backend_error_limit=out_limit)
    if persona_instruction:
        sanitized_prompt_meta["persona_active"] = True
    if _meta_field(prompt_meta, "persona_injected", False):
        sanitized_prompt_meta["persona_injected"] = True

    prompt_user_block = _meta_field(prompt_meta, "user_block_text", "")

    out = {
        "config": _sanitize_obj(asdict(cfg)),
        "input": text_in,
        "input_routed": text_in,
        "seed": seed,
        "turn_index": turn_index,
        "reply": reply,
        "backend": tutor_res.backend,
        "requested_backend": cfg.tutor_backend,
        "effective_backend": tutor_res.backend,
        "tutor_meta": {
            "backend": tutor_res.backend,
            "model": tutor_res.model,
            "latency_ms": tutor_res.latency_ms,
        },
        "prompt_meta": sanitized_prompt_meta,
    }

    if physics is not None:
        out["physics"] = physics
    if mirror_prediction is not None:
        out["mirror_prediction"] = mirror_prediction
    if mirror_meta is not None:
        out["mirror_meta"] = mirror_meta
    sanitized_backend_error = sanitize_runtime_backend_error(backend_error, backend_error_limit=out_limit)
    if sanitized_backend_error:
        out["backend_error"] = sanitized_backend_error if _expose_backend_errors() else "backend_error_redacted"

    return out
