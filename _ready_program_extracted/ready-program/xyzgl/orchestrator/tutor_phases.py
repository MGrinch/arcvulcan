from __future__ import annotations

import inspect
import json
from ..backends.registry import get_tutor_backend, require_real_backends
from ..config import XYZGLConfig
from ..prompting import build_tutor_prompt, enforce_runtime_protocol_policy
from ..router import sanitize_prompt_meta, validate_runtime_backend_result_meta, validate_runtime_backend_result_shape
from .parsing import parse_eval_block, parse_question
from .phases import EvalPhase, TeachPhase
from .policies import TeachingBudget


def _append_backend_error(current: str | None, message: str) -> str:
    return (current + " | " if current else "") + message


def _has_nonempty_backend_text(text: str) -> bool:
    return bool(str(text or "").strip())


_GENERIC_QUESTION = "Q: Can you explain your reasoning step by step?"


def _normalize_question_line(question: str, fallback: str) -> str:
    q = str(question or "").strip() or str(fallback or "").strip()
    if not q:
        q = _GENERIC_QUESTION
    if q.lower().startswith("question:"):
        q = "Q: " + q.split(":", 1)[1].strip()
    elif not q.lower().startswith("q:"):
        q = "Q: " + q
    return q


def _is_generic_question(question: str) -> bool:
    return _normalize_question_line(question, _GENERIC_QUESTION).strip() == _GENERIC_QUESTION


def _default_teach_question(node_title: str) -> str:
    anchor = str(node_title or "").strip() or "this step"
    return f"Q: In your own words, what is the key point of {anchor}?"


def _get_tutor(cfg: XYZGLConfig):
    return get_tutor_backend(cfg)


def _clamp(s: str, n: int) -> str:
    if n <= 0:
        return s
    return s if len(s) <= n else s[:n]


def _json_quote_bounded(text: str | None, max_chars: int) -> str:
    raw = _clamp(str(text or ""), max(1, int(max_chars)))
    return json.dumps(raw, ensure_ascii=False)


def _format_optional_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _join_payload_bounded(parts: list[str], *, max_chars: int) -> str:
    limit = max(1, int(max_chars))
    out: list[str] = []
    used = 0
    for p in parts:
        if p is None:
            continue
        seg = str(p)
        if not seg:
            continue
        remaining = limit - used
        if remaining <= 0:
            break
        if len(seg) > remaining:
            out.append(seg[:remaining])
            used = limit
            break
        out.append(seg)
        used += len(seg)
    if used < limit and (not out or not out[-1].endswith("\n")):
        out.append("\n")
    return "".join(out)


def _generate_tutor(cfg: XYZGLConfig, tutor_prompt: str, *, seed: int | None):
    strict_tutor = require_real_backends()
    backend_error = None
    try:
        tutor = _get_tutor(cfg)
    except Exception as e:
        if strict_tutor:
            raise
        backend_error = f"tutor_backend_config_error: {e}"
        tutor = get_tutor_backend(XYZGLConfig())

    try:
        res = tutor.generate(tutor_prompt, seed=seed)
    except Exception as e:
        if strict_tutor:
            raise
        backend_error = _append_backend_error(backend_error, f"tutor_backend_error: {e}")
        tutor = get_tutor_backend(XYZGLConfig())
        res = tutor.generate(tutor_prompt, seed=seed)
    shape_error = validate_runtime_backend_result_shape(res, role="tutor_backend")
    if shape_error:
        if strict_tutor:
            raise RuntimeError(shape_error)
        backend_error = _append_backend_error(backend_error, shape_error)
        tutor = get_tutor_backend(XYZGLConfig())
        res = tutor.generate(tutor_prompt, seed=seed)
        shape_error = validate_runtime_backend_result_shape(res, role="tutor_backend")
        if shape_error:
            raise RuntimeError(f"stub {shape_error}")
    meta_error = validate_runtime_backend_result_meta(res, role="tutor_backend")
    if meta_error:
        if strict_tutor:
            raise RuntimeError(meta_error)
        backend_error = _append_backend_error(backend_error, meta_error)
        tutor = get_tutor_backend(XYZGLConfig())
        res = tutor.generate(tutor_prompt, seed=seed)
        shape_error = validate_runtime_backend_result_shape(res, role="tutor_backend")
        if shape_error:
            raise RuntimeError(f"stub {shape_error}")
        meta_error = validate_runtime_backend_result_meta(res, role="tutor_backend")
        if meta_error:
            raise RuntimeError(f"stub {meta_error}")
    if not _has_nonempty_backend_text(res.text):
        contract_error = "tutor_backend_contract_error: empty_reply"
        if strict_tutor:
            raise RuntimeError(contract_error)
        backend_error = _append_backend_error(backend_error, contract_error)
        tutor = get_tutor_backend(XYZGLConfig())
        res = tutor.generate(tutor_prompt, seed=seed)
        if not _has_nonempty_backend_text(res.text):
            raise RuntimeError("stub tutor backend produced empty contract reply")
    return res, backend_error


def _compact_grounding_meta(raw: object) -> dict:
    gm = raw if isinstance(raw, dict) else {}
    out = {k: v for k, v in gm.items() if k != "snippets"}
    snippets = gm.get("snippets")
    if isinstance(snippets, list):
        keep = 12
        out["snippet_count"] = len(snippets)
        out["snippets"] = snippets[:keep]
        dropped = len(snippets) - keep
        if dropped > 0:
            out["snippets_truncated"] = dropped
    else:
        out["snippets"] = []
        out["snippet_count"] = 0
    return out


def _prompt_meta(meta, res, *, phase: str | None = None, backend_error: str | None = None, backend_error_limit: int | None = None) -> dict:
    return sanitize_prompt_meta(
        meta,
        grounding=_compact_grounding_meta(meta.grounding_meta),
        tutor_backend=res.backend,
        tutor_model=res.model,
        tutor_latency_ms=res.latency_ms,
        phase=phase,
        backend_error=backend_error,
        backend_error_limit=backend_error_limit,
    )


def _build_tutor_prompt_with_optional_persona(
    user_payload: str,
    *,
    cfg: XYZGLConfig,
    turn_index: int,
    persona_text: str,
):
    kwargs = {"cfg": cfg, "turn_index": turn_index}
    safe_persona_text = str(persona_text or "")
    try:
        prompt_params = inspect.signature(build_tutor_prompt).parameters
    except (TypeError, ValueError):
        prompt_params = {}
    if safe_persona_text and "persona_text" in prompt_params:
        kwargs["persona_text"] = safe_persona_text
    return build_tutor_prompt(user_payload, **kwargs)


def _attach_persona_prompt_meta(prompt_meta: dict, *, persona_injected: bool) -> dict:
    if not persona_injected:
        return prompt_meta
    out = dict(prompt_meta)
    out["persona_injected"] = True
    return out


def _build_teach_phase_kwargs(base_kwargs: dict, *, persona_injected: bool) -> dict:
    out = dict(base_kwargs)
    teach_fields = getattr(TeachPhase, "__dataclass_fields__", {})
    if "persona_injected" in teach_fields:
        out["persona_injected"] = persona_injected
    return out


def _attach_eval_physics_prompt_meta(
    prompt_meta: dict,
    *,
    resonance: float | None,
    mastery: float | None,
    text_similarity: float | None,
) -> dict:
    if resonance is None and mastery is None and text_similarity is None:
        return prompt_meta
    out = dict(prompt_meta)
    out["physics"] = {
        "mastery": mastery,
        "resonance": resonance,
        "text_similarity": text_similarity,
    }
    return out


def _build_eval_phase_kwargs(base_kwargs: dict, *, resonance: float | None, mastery: float | None, text_similarity: float | None) -> dict:
    out = dict(base_kwargs)
    eval_fields = getattr(EvalPhase, "__dataclass_fields__", {})
    for name, value in {
        "resonance": resonance,
        "mastery": mastery,
        "text_similarity": text_similarity,
    }.items():
        if name in eval_fields:
            out[name] = value
    return out


def run_teach_phase(
    *,
    cfg: XYZGLConfig,
    seed: int | None,
    turn_index: int,
    node_id: str,
    node_title: str,
    node_summary: str,
    user_state: str,
    budget: TeachingBudget,
    persona_text: str = "",
) -> TeachPhase:
    """Generate the teaching block + exactly one question."""
    payload_budget = max(512, int(cfg.max_chars_in))
    summary_cap = max(256, payload_budget // 3)
    user_payload = _join_payload_bounded(
        [
            "PHASE: TEACH\n",
            f"NODE_ID: {_clamp(node_id, 128)}\n",
            f"NODE_TITLE: {_clamp(node_title, 256)}\n",
            f"NODE_SUMMARY: {_clamp(node_summary, summary_cap)}\n",
            f"USER_STATE: {_clamp(user_state, 64)}\n",
            f"BUDGET: {budget.min_sentences}-{budget.max_sentences} sentences, {budget.density}\n",
            "\n",
            "Task: Write the teaching block within budget, then ask EXACTLY ONE question prefixed with 'Q:'.\n",
        ],
        max_chars=payload_budget,
    )

    persona_injected = bool(str(persona_text or "").strip())
    tutor_prompt, meta = _build_tutor_prompt_with_optional_persona(
        user_payload,
        cfg=cfg,
        turn_index=turn_index,
        persona_text=persona_text,
    )
    enforce_runtime_protocol_policy(meta, allow_fallback=bool(getattr(cfg, "allow_protocol_fallback", False)))
    tutor_prompt = _clamp(tutor_prompt, cfg.max_chars_in)
    res, backend_error = _generate_tutor(cfg, tutor_prompt, seed=seed)
    teaching, q = parse_question(res.text or "")

    if _is_generic_question(q):
        q = _default_teach_question(node_title)

    teach_kwargs = _build_teach_phase_kwargs(
        {
            "node_id": node_id,
            "user_state": user_state,
            "budget": budget,
            "teaching_block": _clamp(teaching, cfg.max_chars_out),
            "question": _clamp(q, cfg.max_chars_out),
            "prompt_meta": _attach_persona_prompt_meta(
                _prompt_meta(meta, res, backend_error=backend_error, backend_error_limit=cfg.max_chars_out),
                persona_injected=persona_injected,
            ),
        },
        persona_injected=persona_injected,
    )
    return TeachPhase(**teach_kwargs)


def run_probe_phase(
    *,
    cfg: XYZGLConfig,
    seed: int | None,
    turn_index: int,
    node_id: str,
    node_title: str,
    node_summary: str,
    user_state: str,
    pointed_question: str,
    persona_text: str = "",
) -> TeachPhase:
    """Generate a short hint + a pointed question for a PROBE mini-cycle."""
    payload_budget = max(512, int(cfg.max_chars_in))
    summary_cap = max(256, payload_budget // 3)
    question_cap = max(256, payload_budget // 2)
    user_payload = _join_payload_bounded(
        [
            "PHASE: PROBE\n",
            f"NODE_ID: {_clamp(node_id, 128)}\n",
            f"NODE_TITLE: {_clamp(node_title, 256)}\n",
            f"NODE_SUMMARY: {_clamp(node_summary, summary_cap)}\n",
            f"USER_STATE: {_clamp(user_state, 64)}\n",
            "\n",
            "Task: Write 1-3 short sentences as a hint, then ask the pointed question.\n",
            "Use EXACTLY ONE question line prefixed with 'Q:' and keep it close to:\n",
            f"{_clamp(pointed_question, question_cap)}\n",
        ],
        max_chars=payload_budget,
    )

    persona_injected = bool(str(persona_text or "").strip())
    tutor_prompt, meta = _build_tutor_prompt_with_optional_persona(
        user_payload,
        cfg=cfg,
        turn_index=turn_index,
        persona_text=persona_text,
    )
    enforce_runtime_protocol_policy(meta, allow_fallback=bool(getattr(cfg, "allow_protocol_fallback", False)))
    tutor_prompt = _clamp(tutor_prompt, cfg.max_chars_in)
    res, backend_error = _generate_tutor(cfg, tutor_prompt, seed=seed)
    teaching, q = parse_question(res.text or "")
    q = _normalize_question_line(q, pointed_question)
    if _is_generic_question(q):
        q = _normalize_question_line(pointed_question, _GENERIC_QUESTION)

    teach_kwargs = _build_teach_phase_kwargs(
        {
            "node_id": node_id,
            "user_state": user_state,
            "budget": TeachingBudget(min_sentences=1, max_sentences=3, density="light"),
            "teaching_block": _clamp(teaching, cfg.max_chars_out),
            "question": _clamp(q, cfg.max_chars_out),
            "prompt_meta": _attach_persona_prompt_meta(
                _prompt_meta(meta, res, phase="PROBE", backend_error=backend_error, backend_error_limit=cfg.max_chars_out),
                persona_injected=persona_injected,
            ),
        },
        persona_injected=persona_injected,
    )
    return TeachPhase(**teach_kwargs)


def run_eval_phase(
    *,
    cfg: XYZGLConfig,
    seed: int | None,
    turn_index: int,
    node_id: str,
    node_title: str,
    teach: TeachPhase,
    mirror_answer: str | None,
    user_answer: str,
    required_keywords: list[str],
    resonance: float | None = None,
    mastery: float | None = None,
    text_similarity: float | None = None,
    force_close: bool = False,
) -> EvalPhase:
    """Evaluate the learner answer and choose PROBE or CLOSE_NODE."""
    req_list = [str(x).strip()[:80] for x in (required_keywords or []) if str(x).strip()][:64]
    req = ", ".join(req_list)
    payload_budget = max(512, int(cfg.max_chars_in))
    per_block = max(256, payload_budget // 3)
    safe_user_answer = _clamp((user_answer or ""), per_block)
    safe_mirror_answer = _clamp((mirror_answer or ""), per_block)
    safe_teaching_block = _clamp(teach.teaching_block, per_block)
    safe_question = _clamp(teach.question, max(128, payload_budget // 4))
    safe_node_title = _clamp(node_title, 256)
    safe_user_json = _json_quote_bounded(safe_user_answer, per_block)
    safe_mirror_json = _json_quote_bounded(safe_mirror_answer or "<none>", per_block)
    safe_node_title_json = _json_quote_bounded(safe_node_title, 256)
    safe_teaching_json = _json_quote_bounded(safe_teaching_block, per_block)
    safe_question_json = _json_quote_bounded(safe_question, max(128, payload_budget // 4))
    physics_enabled = resonance is not None or mastery is not None or text_similarity is not None
    physics_payload_parts: list[str] = []
    if physics_enabled:
        physics_payload_parts = [
            f"PHYSICS: mastery={_format_optional_metric(mastery)}, resonance={_format_optional_metric(resonance)}, text_similarity={_format_optional_metric(text_similarity)}\n",
            "Use PHYSICS signals to inform evaluation. High resonance (>0.8) = aligned understanding. Low (<0.3) = fundamental gaps.\n",
        ]
    user_payload = _join_payload_bounded(
        [
            "PHASE: EVAL\n",
            f"NODE_ID: {_clamp(node_id, 128)}\n",
            f"NODE_TITLE_JSON: {safe_node_title_json}\n",
            f"REQUIRED_KEYWORDS: {_clamp(req, max(128, payload_budget // 4))}\n",
            "\nTeaching block (JSON string):\n",
            safe_teaching_json + "\n",
            "\nQuestion (JSON string):\n",
            safe_question_json + "\n",
            "\nMirror predicted answer (JSON string):\n",
            safe_mirror_json + "\n",
            "\nReal learner answer (JSON string):\n",
            safe_user_json + "\n",
            "\n",
            *physics_payload_parts,
            "\nTask: Compare mirror vs real; identify missing premises; then output:\n",
            "EVAL: <1-3 sentences>\n",
            "GAPS: <comma-separated or short bullets>\n",
            "NEXT_ACTION: PROBE or CLOSE_NODE\n",
            "Q2: <one pointed question if PROBE>\n",
        ],
        max_chars=payload_budget,
    )

    tutor_prompt, meta = build_tutor_prompt(user_payload, cfg=cfg, turn_index=turn_index)
    enforce_runtime_protocol_policy(meta, allow_fallback=bool(getattr(cfg, "allow_protocol_fallback", False)))
    tutor_prompt = _clamp(tutor_prompt, cfg.max_chars_in)
    res, backend_error = _generate_tutor(cfg, tutor_prompt, seed=seed)
    parsed_text = _clamp(res.text or "", cfg.max_chars_out)
    parsed = parse_eval_block(parsed_text)
    if force_close:
        parsed["next_action"] = "CLOSE_NODE"
    elif str(parsed.get("next_action") or "").strip().upper() == "CLOSE_NODE":
        # Business rule: only deterministic closure gate can close nodes.
        parsed["next_action"] = "PROBE"

    prompt_meta = _attach_eval_physics_prompt_meta(
        _prompt_meta(meta, res, phase="EVAL", backend_error=backend_error, backend_error_limit=cfg.max_chars_out),
        resonance=resonance,
        mastery=mastery,
        text_similarity=text_similarity,
    )
    next_action = str(parsed.get("next_action") or "PROBE").strip().upper()
    next_question = None
    if next_action != "CLOSE_NODE":
        next_question = str(
            parsed.get("next_question") or "Q2: What's the missing step in your reasoning?"
        ).strip()

    eval_kwargs = _build_eval_phase_kwargs(
        {
            "node_id": node_id,
            "user_answer": safe_user_answer,
            "mirror_answer": safe_mirror_answer or None,
            "evaluation": str(parsed.get("evaluation") or "").strip(),
            "gaps": str(parsed.get("gaps") or "").strip(),
            "next_action": next_action,
            "next_question": next_question,
            "prompt_meta": prompt_meta,
        },
        resonance=resonance,
        mastery=mastery,
        text_similarity=text_similarity,
    )
    return EvalPhase(**eval_kwargs)
