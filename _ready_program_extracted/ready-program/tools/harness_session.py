#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import os
import random
import re
import shutil
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from witness.core import WitnessCore
from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import KnowledgeGraph, default_graph, save_graph
from xyzgl.orchestrator.session_loop import run_session

MAX_TURNS_HARD = 64


def _effective_mirror_prompt_mode(cfg: XYZGLConfig) -> str:
    if not bool(getattr(cfg, "enable_mirror", False)):
        return "disabled"
    return "sanitized" if bool(getattr(cfg, "mirror_send_user_content", False)) else "redacted"


def _default_run_id(args: argparse.Namespace, cfg: XYZGLConfig, execution_mode: str, session_seed: int | None) -> str:
    return make_run_id(
        "session",
        {
            "issue": args.issue,
            "requested_seed": int(args.seed),
            "session_seed": session_seed,
            "max_turns": int(args.max_turns),
            "execution_mode": execution_mode,
            "enable_mirror": bool(cfg.enable_mirror),
            "mirror_prompt_mode": _effective_mirror_prompt_mode(cfg),
            "grounding_mode": str(cfg.grounding_mode),
            "grounding_dir": str(cfg.grounding_dir),
            "protocol_path": str(cfg.protocol_path),
            "protocol_reground_every": int(cfg.protocol_reground_every),
            "tutor_backend": str(cfg.tutor_backend),
            "mirror_backend": str(cfg.mirror_backend),
            "enforce_determinism": bool(cfg.enforce_determinism),
        },
    )


def _safe_run_id(value: str) -> str:
    rid = (value or "").strip()
    if not rid:
        raise ValueError("--run-id resolved to empty")
    if Path(rid).is_absolute() or "/" in rid or "\\" in rid or ".." in rid:
        raise ValueError("--run-id must be a simple slug (no path separators or '..')")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", rid):
        raise ValueError("--run-id contains invalid characters")
    return rid


_SIM_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "explain",
    "for", "from", "give", "how", "i", "if", "in", "is", "it", "me", "of", "on", "or", "q",
    "q2", "please", "show", "tell", "the", "this", "to", "what", "when", "where", "which", "why",
    "with", "you", "your",
}


def _context_tokens(text: str, *, limit: int = 8) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9']+", str(text or "").lower()):
        if len(tok) <= 1 or tok in _SIM_STOPWORDS:
            continue
        if tok not in tokens:
            tokens.append(tok)
        if len(tokens) >= limit:
            break
    return tokens


def _stable_rng(*parts: object) -> random.Random:
    payload = "||".join(str(p or "") for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _derive_seed(*parts: object) -> int:
    payload = "||".join(str(p or "") for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def _simulated_user_answer(
    node_id: str,
    question: str,
    required_keywords: list[str],
    *,
    seed: int,
    attempt_index: int = 0,
    prior_questions: list[str] | None = None,
    prior_answers: list[str] | None = None,
) -> str:
    req = [str(kw).strip() for kw in (required_keywords or []) if str(kw).strip()]
    history_q = [str(q or "") for q in (prior_questions or [])][-4:]
    history_a = [str(a or "") for a in (prior_answers or [])][-4:]
    q_tokens = _context_tokens(question)
    history_tokens = _context_tokens(" ".join(history_q + history_a), limit=12)

    rng = _stable_rng(seed, node_id, attempt_index, question, "||".join(history_q), "||".join(history_a))
    req_order = list(req)
    rng.shuffle(req_order)

    if attempt_index <= 0:
        if len(req_order) <= 1:
            included = []
            omitted = req_order
        else:
            included = req_order[:-1]
            omitted = req_order[-1:]
    else:
        included = req_order
        omitted = []

    focus = q_tokens[:3] or history_tokens[:3] or ["concept"]
    connectors = ["because", "so", "which", "means", "therefore", "here"]
    rng.shuffle(connectors)

    parts: list[str] = []
    lead = " and ".join(included) if included else "I need another hint before I can name the key term"
    parts.append(f"For {' / '.join(focus)}, I think {lead}.")

    if attempt_index > 0:
        if history_a:
            bridge = " then ".join(focus[:2]) if len(focus) >= 2 else focus[0]
            parts.append(f"Building on my earlier answer, I can now connect {bridge} to {'; '.join(req)}.")
        elif req:
            parts.append(f"Now I can connect {'; '.join(req)} clearly.")
    elif omitted:
        parts.append("I am still not fully sure about the last missing step yet.")

    if history_q:
        shifted_focus = _context_tokens(history_q[-1], limit=2) or focus[:2]
        parts.append(f"Your follow-up question changed my focus toward {' and '.join(shifted_focus)}.")

    parts.append(f"{connectors[0].capitalize()} {connectors[1]} {connectors[2]}, this is my current explanation.")
    return " ".join(p.strip() for p in parts if p and p.strip())


def _md_fenced(text: str) -> str:
    t = str(text or "")
    t = t.replace("```", "``\\`")
    t = html.escape(t)
    return f"```text\n{t}\n```"


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


def _first_graph_completion_turn(
    initial_graph: KnowledgeGraph,
    turns: list[object],
    *,
    confidence_bump: float = 0.25,
) -> int | None:
    confidence_by_node: dict[str, float] = {}
    for node in list(getattr(initial_graph, "nodes", []) or []):
        node_id = str(getattr(node, "node_id", "") or "").strip()
        if not node_id:
            continue
        try:
            confidence = float(getattr(node, "confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        confidence_by_node[node_id] = max(0.0, min(1.0, confidence))
    if not confidence_by_node or all(value >= 1.0 for value in confidence_by_node.values()):
        return None

    bump = max(0.0, float(confidence_bump))
    for turn in list(turns or []):
        node_id = str(getattr(turn, "node_id", "") or "").strip()
        eval_phase = getattr(turn, "eval", None)
        next_action = str(getattr(eval_phase, "next_action", "") or "").strip().upper()
        if next_action == "CLOSE_NODE" and node_id in confidence_by_node:
            confidence_by_node[node_id] = min(1.0, confidence_by_node[node_id] + bump)
        if confidence_by_node and all(value >= 1.0 for value in confidence_by_node.values()):
            return int(getattr(turn, "turn_index", 0))
    return None


def _classify_session_terminal_state(
    initial_graph: KnowledgeGraph,
    final_graph: KnowledgeGraph,
    turns: list[object],
) -> dict[str, object]:
    completion_turn = _first_graph_completion_turn(initial_graph, turns)
    post_completion_turns: list[int] = []
    if completion_turn is not None:
        for turn in list(turns or []):
            try:
                turn_index = int(getattr(turn, "turn_index", 0))
            except Exception:
                turn_index = 0
            if turn_index > completion_turn:
                post_completion_turns.append(turn_index)

    initial_complete = _graph_fully_mastered(initial_graph)
    final_complete = _graph_fully_mastered(final_graph)
    if post_completion_turns:
        terminal_state = "post_mastery_overrun"
    elif completion_turn is not None or (initial_complete and not turns):
        terminal_state = "graph_complete"
    elif final_complete:
        terminal_state = "graph_complete"
    else:
        terminal_state = "max_turns_exhausted"

    return {
        "initial_graph_complete": initial_complete,
        "final_graph_complete": final_complete,
        "completion_turn_index": completion_turn,
        "post_completion_turns": post_completion_turns,
        "terminal_state": terminal_state,
    }


def _cleanup_run_dir(run_dir: Path | None) -> None:
    if run_dir is None or not run_dir.exists():
        return
    try:
        if any(run_dir.iterdir()):
            return
    except OSError:
        return
    try:
        shutil.rmtree(run_dir)
    except OSError:
        pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--max-turns", type=int, default=6)
    p.add_argument("--protocol-reground-every", type=int, default=None, help="Re-ground ROLE_PROTOCOL every N turns (default: config default)")
    p.add_argument("--run-id", help="Optional run id (default: stable hash of invocation)")
    p.add_argument("--enable-mirror", action="store_true")
    p.add_argument("--grounding", action="store_true", help="Enable local grounding during the run")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2
    if int(args.max_turns) < 1:
        print("INCOMPLETE: --max-turns must be >= 1")
        return 2
    if int(args.max_turns) > MAX_TURNS_HARD:
        print(f"INCOMPLETE: --max-turns exceeds hard cap ({args.max_turns} > {MAX_TURNS_HARD})")
        return 2

    env_cfg = XYZGLConfig.from_env()
    if env_cfg.enforce_determinism:
        random.seed(args.seed)
    else:
        random.seed()

    mirror_enabled = bool(args.enable_mirror) or env_cfg.enable_mirror
    mirror_send_user_content = bool(env_cfg.mirror_send_user_content)

    reg_every = args.protocol_reground_every
    if reg_every is None:
        reg_every = env_cfg.protocol_reground_every

    grounding_mode = env_cfg.grounding_mode
    if args.grounding:
        grounding_mode = "local"

    ambient_root_seed: int | None = None
    if env_cfg.enforce_determinism:
        execution_mode = "deterministic"
        seed_contract = "requested-seed"
        session_seed = args.seed
        simulator_seed = args.seed
        cfg = XYZGLConfig(
            tutor_backend="stub",
            mirror_backend="stub",
            enable_mirror=mirror_enabled,
            mirror_send_user_content=mirror_send_user_content,
            protocol_path=env_cfg.protocol_path,
            protocol_reground_every=int(reg_every),
            grounding_mode=grounding_mode,
            grounding_dir=env_cfg.grounding_dir,
            grounding_max_snippets=env_cfg.grounding_max_snippets,
            grounding_max_chars=env_cfg.grounding_max_chars,
            enforce_determinism=True,
            max_chars_in=env_cfg.max_chars_in,
            max_chars_out=env_cfg.max_chars_out,
            llm_backend="stub",
        )
    else:
        execution_mode = "ambient"
        seed_contract = "ambient-root-derived"
        ambient_root_seed = random.SystemRandom().randint(0, 2**31 - 1)
        session_seed = _derive_seed("session", ambient_root_seed, args.issue, args.seed, args.max_turns, reg_every, grounding_mode)
        simulator_seed = _derive_seed("simulator", ambient_root_seed, args.issue, args.seed, args.max_turns, reg_every, grounding_mode)
        cfg = XYZGLConfig(
            tutor_backend=env_cfg.tutor_backend,
            mirror_backend=env_cfg.mirror_backend,
            enable_mirror=mirror_enabled,
            mirror_send_user_content=mirror_send_user_content,
            tutor_model=env_cfg.tutor_model,
            mirror_model=env_cfg.mirror_model,
            ollama_host=env_cfg.ollama_host,
            allow_remote_ollama=env_cfg.allow_remote_ollama,
            protocol_path=env_cfg.protocol_path,
            protocol_reground_every=int(reg_every),
            grounding_mode=grounding_mode,
            grounding_dir=env_cfg.grounding_dir,
            grounding_max_snippets=env_cfg.grounding_max_snippets,
            grounding_max_chars=env_cfg.grounding_max_chars,
            enforce_determinism=False,
            max_chars_in=env_cfg.max_chars_in,
            max_chars_out=env_cfg.max_chars_out,
            llm_backend=env_cfg.llm_backend,
        )

    try:
        run_id = _safe_run_id(args.run_id or _default_run_id(args, cfg, execution_mode, session_seed))
    except ValueError as e:
        print(f"INCOMPLETE: {e}")
        return 2

    run_dir: Path | None = None
    try:
        run_dir = allocate_run_dir(run_id)
        graph = default_graph()
        node_attempts: dict[str, int] = {}
        node_questions: dict[str, list[str]] = {}
        node_answers: dict[str, list[str]] = {}

        def input_provider(prompt: str):
            lines = (prompt or "").split("\n", 4)
            node_id_from_prompt = ""
            title = ""
            for ln in lines[:4]:
                low = ln.strip().lower()
                if low.startswith("node_id:"):
                    node_id_from_prompt = ln.split(":", 1)[1].strip()
                elif low.startswith("node:"):
                    title = ln.split(":", 1)[1].strip()
            node_id = "unknown"
            required = []
            if node_id_from_prompt:
                n = graph.get(node_id_from_prompt)
                if n is not None:
                    node_id = n.node_id
                    required = n.required_keywords
            if not required:
                for n in graph.nodes:
                    if n.title == title:
                        node_id = n.node_id
                        required = n.required_keywords
                        break
            attempt_index = node_attempts.get(node_id, 0)
            prior_questions = list(node_questions.get(node_id, []))
            prior_answers = list(node_answers.get(node_id, []))
            question_text = next((ln.strip() for ln in reversed((prompt or "").splitlines()) if ln.strip()), prompt)
            if attempt_index <= 0:
                if required:
                    ans = f"{required[0]}."
                else:
                    ans = "Need hint."
                typing_ms = 16000
                sim_mode = "incomplete_short"
            else:
                ans = _simulated_user_answer(
                    node_id,
                    question_text,
                    required,
                    seed=simulator_seed,
                    attempt_index=attempt_index,
                    prior_questions=prior_questions,
                    prior_answers=prior_answers,
                )
                if len(ans.strip()) < 60:
                    ans = ans.strip() + " I can explain the full idea clearly now."
                typing_ms = 3200 + (min(attempt_index, 4) * 700)
                sim_mode = "complete_contextual"
            node_attempts[node_id] = attempt_index + 1
            node_questions.setdefault(node_id, []).append(question_text)
            node_answers.setdefault(node_id, []).append(ans)
            return ans, {
                "typing_ms": typing_ms,
                "attempt_index": attempt_index,
                "simulated_mode": sim_mode,
                "simulated_node_id": node_id,
            }

        session_report, graph2 = run_session(
            session_id=run_id,
            cfg=cfg,
            seed=session_seed,
            max_turns=args.max_turns,
            graph=graph,
            input_provider=input_provider,
        )

        wc = WitnessCore()
        event = wc.make_event(args.issue, {"session_report": session_report.to_json()})
        wc.write_event_json(event, str(run_dir / "session_report.json"))

        save_graph(graph2, run_dir / "knowledge_graph.json")

        terminal_info = _classify_session_terminal_state(graph, graph2, session_report.turns)
        last = session_report.turns[-1] if session_report.turns else None
        summary_md = (
            "# Session Summary\n\n"
            f"- issue: `{args.issue}`\n"
            f"- requested_seed: `{args.seed}`\n"
            f"- execution_mode: `{execution_mode}`\n"
            f"- enforce_determinism: `{str(cfg.enforce_determinism).lower()}`\n"
            f"- seed_contract: `{seed_contract}`\n"
            f"- ambient_root_seed: `{ambient_root_seed}`\n"
            f"- session_seed: `{session_seed}`\n"
            f"- simulator_seed: `{simulator_seed}`\n"
            f"- run_id: `{run_id}`\n"
            f"- turns: `{len(session_report.turns)}`\n"
            f"- terminal_state: `{terminal_info['terminal_state']}`\n"
            f"- completion_turn_index: `{terminal_info['completion_turn_index']}`\n"
            f"- post_completion_turns: `{terminal_info['post_completion_turns']}`\n"
            f"- enable_mirror: `{str(cfg.enable_mirror).lower()}`\n"
            f"- mirror_backend: `{cfg.mirror_backend}`\n"
            f"- mirror_send_user_content: `{str(bool(getattr(cfg, 'mirror_send_user_content', False))).lower()}`\n"
            f"- mirror_prompt_mode: `{_effective_mirror_prompt_mode(cfg)}`\n"
            f"- protocol_path: `{cfg.protocol_path}`\n"
            f"- protocol_reground_every: `{cfg.protocol_reground_every}`\n"
            f"- grounding_mode: `{cfg.grounding_mode}`\n"
            f"- grounding_dir: `{cfg.grounding_dir}`\n"
            f"- grounding_max_snippets: `{cfg.grounding_max_snippets}`\n"
            f"- grounding_max_chars: `{cfg.grounding_max_chars}`\n\n"
            "## Last Turn\n\n"
            + (f"**Node:** {_md_fenced(last.node_title)}\n\n" if last else "")
            + (f"**Tutor State:** `{last.teach.user_state}`\n\n" if last else "")
            + (f"**Post-Eval State:** `{last.user_state}`\n\n" if last else "")
            + (f"**Tutor Question:** {_md_fenced(last.teach.question)}\n\n" if last else "")
            + (f"**User Answer:** {_md_fenced(last.eval.user_answer)}\n\n" if last else "")
        )
        (run_dir / "session_summary.md").write_text(summary_md, encoding="utf-8")

        run_meta = {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "requested_seed": args.seed,
            "execution_mode": execution_mode,
            "enforce_determinism": cfg.enforce_determinism,
            "seed_contract": seed_contract,
            "ambient_root_seed": ambient_root_seed,
            "session_seed": session_seed,
            "simulator_seed": simulator_seed,
            "enable_mirror": bool(cfg.enable_mirror),
            "mirror_backend": cfg.mirror_backend,
            "mirror_send_user_content": bool(getattr(cfg, "mirror_send_user_content", False)),
            "mirror_prompt_mode": _effective_mirror_prompt_mode(cfg),
            "protocol_path": str(cfg.protocol_path),
            "protocol_reground_every": int(cfg.protocol_reground_every),
            "grounding_mode": str(cfg.grounding_mode),
            "grounding_dir": str(cfg.grounding_dir),
            "grounding_max_snippets": int(cfg.grounding_max_snippets),
            "grounding_max_chars": int(cfg.grounding_max_chars),
            "deterministic": bool(cfg.enforce_determinism),
            "terminal_state": terminal_info["terminal_state"],
            "initial_graph_complete": terminal_info["initial_graph_complete"],
            "final_graph_complete": terminal_info["final_graph_complete"],
            "completion_turn_index": terminal_info["completion_turn_index"],
            "post_completion_turns": terminal_info["post_completion_turns"],
            "outputs": ["session_report.json", "knowledge_graph.json", "session_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        }
        write_json(run_dir / "run.json", run_meta)

        if terminal_info["terminal_state"] == "post_mastery_overrun":
            print(f"FAIL: post-mastery turns {terminal_info['post_completion_turns']} detected in {run_dir}")
            return 1

        print(f"PASS: wrote outputs to {run_dir}")
        return 0
    except Exception as e:
        _cleanup_run_dir(run_dir)
        print(f"INCOMPLETE: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
