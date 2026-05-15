from __future__ import annotations

from dataclasses import dataclass, replace

from ..config import XYZGLConfig
from ..knowledge.graph import KnowledgeGraph, load_graph, save_graph
from ..knowledge.heuristics import select_next_node
from ..knowledge.update import close_node
from ..router import _sanitize_obj, sanitize_prompt_meta
from .policies import infer_user_state, required_keywords_audit, teaching_budget
from .turn import EvalPhase, TeachPhase, run_eval_phase, run_mirror_prediction, run_probe_phase, run_teach_phase

MAX_SESSION_TURNS = 256
# Session reports must remain faithful to the executed session outcome.
# Keep export and in-memory turn retention aligned with the execution cap.
MAX_SESSION_EXPORT_TURNS = MAX_SESSION_TURNS
MAX_SESSION_IN_MEMORY_TURNS = MAX_SESSION_TURNS
MAX_SESSION_EXPORT_TEXT_CHARS = 2_000


def _graph_fully_mastered(graph: KnowledgeGraph) -> bool:
    nodes = list(getattr(graph, "nodes", []) or [])
    if not nodes:
        return True
    for node in nodes:
        try:
            confidence = float(getattr(node, "confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        if confidence < 1.0:
            return False
    return True


def _clip_text(value: object, *, max_chars: int = MAX_SESSION_EXPORT_TEXT_CHARS) -> str:
    s = str(value or "")
    return s if len(s) <= max_chars else s[:max_chars]


def _sanitize_session_prompt_meta(meta: object) -> dict:
    if not isinstance(meta, dict):
        return {}
    out = sanitize_prompt_meta(meta, backend_error_limit=MAX_SESSION_EXPORT_TEXT_CHARS)
    for key in ("persona_active", "persona_injected"):
        if key in meta:
            out[key] = bool(meta.get(key))
    if "physics" in meta:
        physics = _sanitize_obj(meta.get("physics"))
        if isinstance(physics, dict):
            out["physics"] = physics
    if "continuity" in meta:
        continuity = _sanitize_obj(meta.get("continuity"))
        if isinstance(continuity, dict):
            out["continuity"] = continuity
    return out


def _attach_turn_continuity_prompt_meta(
    prompt_meta: dict | None,
    *,
    turn_kind: str,
    state_source: str,
    carried_user_state: str,
    source_turn_index: int | None,
    source_question: str | None = None,
) -> dict:
    out = dict(prompt_meta or {})
    continuity = {
        "turn_kind": _clip_text(turn_kind, max_chars=32),
        "state_source": _clip_text(state_source, max_chars=64),
        "carried_user_state": _clip_text(carried_user_state, max_chars=64),
        "source_turn_index": source_turn_index,
    }
    if source_question not in (None, ""):
        continuity["source_question"] = _clip_text(source_question)
    out["continuity"] = continuity
    return out


def _sanitize_export_value(value: object):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[_clip_text(k, max_chars=128)] = _sanitize_export_value(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize_export_value(v) for v in value]
    return _clip_text(value)


@dataclass(frozen=True)
class TurnRecord:
    """One orchestrated turn worth of artifacts."""

    turn_index: int
    node_id: str
    node_title: str
    user_state: str
    teach: TeachPhase
    mirror_answer: str | None
    mirror_meta: dict | None
    eval: EvalPhase
    telemetry: dict | None = None
    close_gate: dict | None = None
    resonance: float | None = None
    mastery: float | None = None
    text_similarity: float | None = None
    mastery_delta: float | None = None


@dataclass(frozen=True)
class SessionReport:
    session_id: str
    seed: int | None
    max_turns: int
    turns: list[TurnRecord]

    def to_json(self) -> dict:
        turns_out = []
        for tr in self.turns[:MAX_SESSION_EXPORT_TURNS]:
            next_action = _clip_text(tr.eval.next_action, max_chars=64)
            next_question = None if next_action == "CLOSE_NODE" else _clip_text(tr.eval.next_question)
            turn_dict = {
                "turn_index": tr.turn_index,
                "node_id": _clip_text(tr.node_id, max_chars=256),
                "node_title": _clip_text(tr.node_title, max_chars=512),
                "user_state": _clip_text(tr.teach.user_state, max_chars=64),
                "teach": {
                    "user_state": _clip_text(tr.teach.user_state, max_chars=64),
                    "budget": {
                        "min_sentences": int(tr.teach.budget.min_sentences),
                        "max_sentences": int(tr.teach.budget.max_sentences),
                        "density": _clip_text(tr.teach.budget.density, max_chars=32),
                    },
                    "state_branch_surface": "metadata",
                    "teaching_block": _clip_text(tr.teach.teaching_block),
                    "question": _clip_text(tr.teach.question),
                    "prompt_meta": _sanitize_session_prompt_meta(tr.teach.prompt_meta),
                },
                "mirror": {
                    "answer": _clip_text(tr.mirror_answer) if tr.mirror_answer is not None else None,
                    "meta": tr.mirror_meta,
                },
                "eval": {
                    "user_answer": _clip_text(tr.eval.user_answer),
                    "mirror_answer": _clip_text(tr.eval.mirror_answer) if tr.eval.mirror_answer is not None else None,
                    "evaluation": _clip_text(tr.eval.evaluation),
                    "gaps": _clip_text(tr.eval.gaps),
                    "next_action": next_action,
                    "next_question": next_question,
                    "inferred_user_state": _clip_text(tr.user_state, max_chars=64),
                    "prompt_meta": _sanitize_session_prompt_meta(tr.eval.prompt_meta),
                },
                "telemetry": _sanitize_export_value(tr.telemetry) or {},
                "close_gate": _sanitize_export_value(tr.close_gate) or {
                    "required_keywords": [],
                    "matched_keywords": [],
                    "missing_keywords": [],
                    "satisfied": False,
                },
            }
            if tr.resonance is not None:
                turn_dict["physics"] = {
                    "resonance": round(tr.resonance, 4),
                    "mastery": round(tr.mastery, 4) if tr.mastery is not None else None,
                    "text_similarity": round(tr.text_similarity, 4) if tr.text_similarity is not None else None,
                    "mastery_delta": round(tr.mastery_delta, 4) if tr.mastery_delta is not None else None,
                }
            turns_out.append(turn_dict)
        return {
            "schema_version": "session_report@1",
            "session_id": self.session_id,
            "seed": self.seed,
            "max_turns": self.max_turns,
            "turns": turns_out,
        }


def run_session(
    *,
    session_id: str,
    cfg: XYZGLConfig,
    seed: int | None,
    max_turns: int,
    graph: KnowledgeGraph,
    input_provider,
) -> tuple[SessionReport, KnowledgeGraph]:
    """Run a multi-turn orchestrated session.

    `input_provider(prompt: str) -> (answer: str, telemetry: dict)`

    Notes:
      - The Tutor is called for TEACH and EVAL phases.
      - The Mirror is optional.
      - Node closure is determined deterministically by `required_keywords_satisfied`.
    """

    effective_max_turns = min(max(0, int(max_turns)), MAX_SESSION_TURNS)
    turns: list[TurnRecord] = []
    last_node_id: str | None = None
    active_node_id: str | None = None
    active_teach: TeachPhase | None = None
    pending_probe_question: str | None = None
    pending_probe_user_state: str | None = None
    session_user_state: str | None = None
    last_turn_index: int | None = None
    answer_resonance: float | None = None
    answer_text_sim: float | None = None

    litho = None
    if cfg.lithosphere_enabled:
        from ..knowledge.embeddings import compute_text_similarity, text_to_vector
        from ..knowledge.lithosphere import Lithosphere

        litho = Lithosphere(
            embed_dim=cfg.lithosphere_embed_dim,
            grains=cfg.lithosphere_grains,
            seed=cfg.lithosphere_seed if cfg.lithosphere_seed is not None else (seed if seed is not None else 42),
        )

    for turn_index in range(effective_max_turns):
        if _graph_fully_mastered(graph):
            active_node_id = None
            active_teach = None
            pending_probe_question = None
            pending_probe_user_state = None
            break

        # Select (or keep) the active node.
        if active_node_id is None:
            selection_seed = None if seed is None else int(seed) + int(turn_index) + 1
            node = select_next_node(graph, seed=selection_seed, avoid_node_id=last_node_id)
            last_node_id = node.node_id
            active_node_id = node.node_id
            answer_resonance = None
            answer_text_sim = None

            topic_resonance = None
            if litho is not None:
                topic_vec = text_to_vector(node.summary, dim=cfg.lithosphere_embed_dim)
                litho.get_or_create(node.node_id, topic_vec, node.summary)

            if session_user_state in {"flow", "frustrated"}:
                state_hint = session_user_state
                teach_state_source = "carried_forward"
                teach_source_turn_index = last_turn_index
            else:
                state_hint = "flow" if node.confidence > 0.5 else "frustrated"
                teach_state_source = "bootstrap_confidence"
                teach_source_turn_index = None
            budget = teaching_budget(state_hint)

            persona_text = ""
            if cfg.persona_enabled and litho is not None:
                from ..persona import build_persona_instruction, persona_from_config

                pcfg = persona_from_config(cfg)
                if pcfg is not None:
                    current_mastery = litho.get_mastery(node.node_id)
                    persona_text = build_persona_instruction(
                        pcfg,
                        mastery=current_mastery,
                        resonance=answer_resonance or 0.0,
                    )

            active_teach = run_teach_phase(
                cfg=cfg,
                seed=seed,
                turn_index=turn_index,
                node_id=node.node_id,
                node_title=node.title,
                node_summary=node.summary,
                user_state=state_hint,
                budget=budget,
                persona_text=persona_text,
            )
            active_teach = replace(
                active_teach,
                prompt_meta=_attach_turn_continuity_prompt_meta(
                    active_teach.prompt_meta,
                    turn_kind="teach",
                    state_source=teach_state_source,
                    carried_user_state=state_hint,
                    source_turn_index=teach_source_turn_index,
                ),
            )
            pending_probe_question = None
            pending_probe_user_state = None
        else:
            node = graph.get(active_node_id)
            if node is None:
                active_node_id = None
                active_teach = None
                pending_probe_question = None
                pending_probe_user_state = None
                continue

        if active_teach is None:
            # Keep the loop resilient even when upstream state is inconsistent.
            active_node_id = None
            pending_probe_question = None
            pending_probe_user_state = None
            continue

        # For PROBE turns, generate a short hint + pointed question (new prompt meta for this turn).
        if pending_probe_question:
            probe_user_state = pending_probe_user_state or session_user_state or active_teach.user_state or "frustrated"
            persona_text = ""
            if cfg.persona_enabled and litho is not None:
                from ..persona import build_persona_instruction, persona_from_config

                pcfg = persona_from_config(cfg)
                if pcfg is not None:
                    current_mastery = litho.get_mastery(node.node_id)
                    persona_text = build_persona_instruction(
                        pcfg,
                        mastery=current_mastery,
                        resonance=answer_resonance or 0.0,
                    )

            active_teach = run_probe_phase(
                cfg=cfg,
                seed=seed,
                turn_index=turn_index,
                node_id=node.node_id,
                node_title=node.title,
                node_summary=node.summary,
                user_state=probe_user_state,
                pointed_question=pending_probe_question,
                persona_text=persona_text,
            )
            active_teach = replace(
                active_teach,
                prompt_meta=_attach_turn_continuity_prompt_meta(
                    active_teach.prompt_meta,
                    turn_kind="probe",
                    state_source="probe_followup",
                    carried_user_state=probe_user_state,
                    source_turn_index=last_turn_index,
                    source_question=pending_probe_question,
                ),
            )
            pending_probe_question = None
            pending_probe_user_state = None

        teach = active_teach
        asked_question = teach.question

        mirror_answer, mirror_meta = run_mirror_prediction(
            cfg=cfg,
            seed=seed,
            node_title=node.title,
            teaching_block=teach.teaching_block,
            question=asked_question,
        )

        # Prompt user
        user_prompt = (
            f"NODE_ID: {node.node_id}\n"
            f"NODE: {node.title}\n\n"
            f"{teach.teaching_block}\n\n{asked_question}\n"
        )
        user_answer, telemetry = input_provider(user_prompt)
        if not isinstance(user_answer, str):
            user_answer = str(user_answer or "")
        if isinstance(telemetry, dict):
            telemetry_dict = dict(telemetry)
        elif telemetry is None:
            telemetry_dict = {}
        else:
            telemetry_dict = {"raw": str(telemetry)}

        answer_resonance = None
        answer_text_sim = None
        if litho is not None:
            answer_vec = text_to_vector(user_answer, dim=cfg.lithosphere_embed_dim)
            answer_resonance = litho.compute_resonance(node.node_id, answer_vec)
            answer_text_sim = compute_text_similarity(user_answer, node.summary)

        typing_ms = telemetry_dict.get("typing_ms") if isinstance(telemetry_dict, dict) else None
        user_state = infer_user_state(user_answer, typing_ms=typing_ms)
        session_user_state = user_state

        # Close decision is deterministic for v0
        close_gate = required_keywords_audit(node.required_keywords, user_answer)
        should_close = bool(close_gate.get("satisfied"))

        graph_node = graph.get(node.node_id)
        old_mastery = graph_node.confidence if graph_node is not None else 0.0
        new_mastery = old_mastery
        if litho is not None and answer_resonance is not None:
            if (
                answer_resonance > cfg.resonance_high_threshold
                or (answer_text_sim or 0.0) > cfg.similarity_high_threshold
            ):
                new_mastery = min(1.0, old_mastery + cfg.mastery_increment)

        ev = run_eval_phase(
            cfg=cfg,
            seed=seed,
            turn_index=turn_index,
            node_id=node.node_id,
            node_title=node.title,
            teach=teach,
            mirror_answer=mirror_answer,
            user_answer=user_answer,
            required_keywords=node.required_keywords,
            force_close=should_close,
            resonance=answer_resonance,
            mastery=new_mastery,
            text_similarity=answer_text_sim,
        )
        if ev.next_action == "CLOSE_NODE" and ev.next_question is not None:
            ev = replace(ev, next_question=None)

        if litho is not None and answer_resonance is not None:
            from ..knowledge.update import update_mastery_from_resonance

            graph = update_mastery_from_resonance(
                graph,
                node.node_id,
                resonance=answer_resonance,
                text_similarity=answer_text_sim or 0.0,
                turn_index=turn_index,
                high_resonance_threshold=cfg.resonance_high_threshold,
                high_similarity_threshold=cfg.similarity_high_threshold,
                mastery_increment=cfg.mastery_increment,
            )
            if litho is not None:
                litho.update_mastery(
                    node.node_id,
                    resonance=answer_resonance,
                    text_similarity=answer_text_sim or 0.0,
                )
        graph_node = graph.get(node.node_id)
        new_mastery = graph_node.confidence if graph_node is not None else 0.0
        mastery_delta = new_mastery - old_mastery

        if len(turns) < MAX_SESSION_IN_MEMORY_TURNS:
            turns.append(
                TurnRecord(
                    turn_index=turn_index,
                    node_id=node.node_id,
                    node_title=node.title,
                    user_state=user_state,
                    teach=TeachPhase(
                        node_id=teach.node_id,
                        user_state=teach.user_state,
                        budget=teach.budget,
                        teaching_block=teach.teaching_block,
                        question=asked_question,
                        prompt_meta=teach.prompt_meta,
                    ),
                    mirror_answer=mirror_answer,
                    mirror_meta=mirror_meta,
                    eval=ev,
                    telemetry=telemetry_dict,
                    close_gate=close_gate,
                    resonance=answer_resonance,
                    mastery=new_mastery if litho is not None else None,
                    text_similarity=answer_text_sim,
                    mastery_delta=mastery_delta if litho is not None else None,
                )
            )

        last_turn_index = turn_index
        if ev.next_action == "CLOSE_NODE":
            graph = close_node(graph, node.node_id, turn_index=turn_index)
            active_node_id = None
            active_teach = None
            pending_probe_question = None
            pending_probe_user_state = None
        else:
            # Continue probing same node next turn using the learner state inferred from this answer.
            pending_probe_question = ev.next_question
            pending_probe_user_state = user_state

    return SessionReport(session_id=session_id, seed=seed, max_turns=effective_max_turns, turns=turns), graph
