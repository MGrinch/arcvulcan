#!/usr/bin/env python3
from __future__ import annotations

"""Seed sweep stability check.

Runs the same session-harness input across a range of seeds and reports variance
in the live session loop rather than a single route_turn proxy.

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

import argparse
import hashlib
import math
import os
import random
import shutil
import statistics
import sys
import unicodedata
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.session_loop import run_session


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFC", str(text or ""))
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in t.split("\n")]
    return "\n".join(lines).strip()


def _effective_mirror_prompt_mode(cfg: XYZGLConfig) -> str:
    if not bool(getattr(cfg, "enable_mirror", False)):
        return "disabled"
    return "sanitized" if bool(getattr(cfg, "mirror_send_user_content", False)) else "redacted"


def _run_id(args: argparse.Namespace, cfg: XYZGLConfig, canonical_input: str, execution_mode: str) -> str:
    return make_run_id(
        "seed-sweep",
        {
            "issue": args.issue,
            "requested_seed": int(args.seed),
            "seed_start": int(args.seed_start),
            "seed_end": int(args.seed_end),
            "turn_index": int(args.turn_index),
            "max_unique_replies": int(args.max_unique_replies),
            "execution_mode": execution_mode,
            "enforce_determinism": bool(cfg.enforce_determinism),
            "enable_mirror": bool(cfg.enable_mirror),
            "tutor_backend": str(cfg.tutor_backend),
            "mirror_backend": str(cfg.mirror_backend),
            "mirror_prompt_mode": _effective_mirror_prompt_mode(cfg),
            "canonical_input": canonical_input,
        },
    )


def _select_kth(values: list[int], k: int) -> int:
    arr = list(values)
    lo = 0
    hi = len(arr) - 1
    k = max(0, min(k, hi))
    while lo <= hi:
        pivot = arr[(lo + hi) // 2]
        i, j = lo, hi
        while i <= j:
            while arr[i] < pivot:
                i += 1
            while arr[j] > pivot:
                j -= 1
            if i <= j:
                arr[i], arr[j] = arr[j], arr[i]
                i += 1
                j -= 1
        if k <= j:
            hi = j
        elif k >= i:
            lo = i
        else:
            return int(arr[k])
    return int(arr[k])


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    k = max(0, math.ceil(0.95 * len(values)) - 1)
    if k >= len(values):
        k = len(values) - 1
    return _select_kth(values, k)


def _normalize_reply(text: str) -> str:
    t = _normalize_text(text).lower()
    t = " ".join(t.split())
    return t.rstrip(".,;:!?")


def _hash_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _derive_seed(*parts: object) -> int:
    payload = "||".join(str(p or "") for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def _effective_session_seed(*, enforce_determinism: bool, sample_seed: int, ambient_root_seed: int | None) -> int:
    if enforce_determinism:
        return int(sample_seed)
    if ambient_root_seed is None:
        raise ValueError("ambient_root_seed is required when determinism is disabled")
    return _derive_seed("ambient-seed-sweep", ambient_root_seed, sample_seed)


def _extract_node(prompt: str, graph) -> tuple[str, list[str]]:
    node_id = ""
    title = ""
    for ln in (prompt or "").splitlines()[:4]:
        low = ln.strip().lower()
        if low.startswith("node_id:"):
            node_id = ln.split(":", 1)[1].strip()
        elif low.startswith("node:"):
            title = ln.split(":", 1)[1].strip()
    if node_id:
        node = graph.get(node_id)
        if node is not None:
            return node.node_id, [str(kw).strip() for kw in (node.required_keywords or []) if str(kw).strip()]
    for node in graph.nodes:
        if node.title == title:
            return node.node_id, [str(kw).strip() for kw in (node.required_keywords or []) if str(kw).strip()]
    return "unknown", []


def _build_input_provider(*, graph, canonical_input: str, target_turn: int):
    state = {"call_index": 0}
    fallback = canonical_input.splitlines()[0].strip() if canonical_input.strip() else "I need another hint."

    def input_provider(prompt: str):
        idx = state["call_index"]
        state["call_index"] += 1
        _node_id, required = _extract_node(prompt, graph)
        if idx < target_turn:
            answer = fallback
        else:
            answer = canonical_input or fallback
            missing = [kw for kw in required if kw and kw.lower() not in answer.lower()]
            if missing:
                answer = (answer + "\n" + " ".join(missing)).strip()
        return answer, {"typing_ms": 1500, "canonical_input": canonical_input, "input_turn_index": idx}

    return input_provider


def _aggregate_errors(*parts: object) -> str | None:
    errors: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            err = part.get("backend_error") or part.get("error")
            if err:
                err_s = str(err).strip()
                if err_s and err_s not in errors:
                    errors.append(err_s)
        elif part:
            err_s = str(part).strip()
            if err_s and err_s not in errors:
                errors.append(err_s)
    return " | ".join(errors) if errors else None


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
    p = argparse.ArgumentParser(prog="seed_sweep")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--seed-start", type=int, default=1)
    p.add_argument("--seed-end", type=int, default=25)
    p.add_argument("--turn-index", type=int, default=0)
    p.add_argument("--text", default="Explain 2F vs 1F in welding")
    p.add_argument("--max-unique-replies", type=int, default=5, help="fail if unique replies exceed this")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2
    try:
        args.seed_start = int(args.seed_start)
        args.seed_end = int(args.seed_end)
        args.turn_index = int(args.turn_index)
        args.max_unique_replies = int(args.max_unique_replies)
    except Exception:
        print("INCOMPLETE: invalid numeric arguments")
        return 2
    if args.seed_start > args.seed_end:
        print("INCOMPLETE: --seed-start must be <= --seed-end")
        return 2
    if args.turn_index < 0:
        print("INCOMPLETE: --turn-index must be >= 0")
        return 2
    if args.max_unique_replies < 0:
        print("INCOMPLETE: --max-unique-replies must be >= 0")
        return 2

    canonical_input = _normalize_text(args.text)
    env_cfg = XYZGLConfig.from_env()
    ambient_root_seed: int | None = None
    if env_cfg.enforce_determinism:
        random.seed(args.seed)
        execution_mode = "deterministic"
        seed_contract = "per-seed"
        cfg = XYZGLConfig(
            tutor_backend="stub",
            mirror_backend="stub",
            enable_mirror=bool(env_cfg.enable_mirror),
            mirror_send_user_content=env_cfg.mirror_send_user_content,
            protocol_path=env_cfg.protocol_path,
            protocol_reground_every=env_cfg.protocol_reground_every,
            grounding_mode=env_cfg.grounding_mode,
            grounding_dir=env_cfg.grounding_dir,
            grounding_max_snippets=env_cfg.grounding_max_snippets,
            grounding_max_chars=env_cfg.grounding_max_chars,
            enforce_determinism=True,
            max_chars_in=env_cfg.max_chars_in,
            max_chars_out=env_cfg.max_chars_out,
            llm_backend="stub",
        )
    else:
        random.seed()
        execution_mode = "ambient"
        seed_contract = "ambient-derived"
        ambient_root_seed = random.SystemRandom().randint(0, 2**31 - 1)
        cfg = env_cfg

    run_dir: Path | None = None
    try:
        run_id = _run_id(
            args,
            cfg,
            canonical_input,
            execution_mode if ambient_root_seed is None else f"{execution_mode}:{ambient_root_seed}",
        )
        run_dir = allocate_run_dir(run_id)
        samples: list[dict] = []
        reply_texts: list[str] = []
        latencies: list[int] = []
        backend_errors: list[str] = []
        mirror_errors: list[str] = []
        empty_reply_count = 0
        target_turn = args.turn_index

        for s in range(args.seed_start, args.seed_end + 1):
            session_seed = _effective_session_seed(
                enforce_determinism=bool(cfg.enforce_determinism),
                sample_seed=s,
                ambient_root_seed=ambient_root_seed,
            )
            graph = default_graph()
            provider = _build_input_provider(graph=graph, canonical_input=canonical_input, target_turn=target_turn)
            session_report, _graph2 = run_session(
                session_id=f"{run_id}-seed-{s}",
                cfg=cfg,
                seed=session_seed,
                max_turns=max(1, target_turn + 1),
                graph=graph,
                input_provider=provider,
            )
            if len(session_report.turns) <= target_turn:
                print(f"INCOMPLETE: session ended before target turn for seed {s}")
                return 2

            turn = session_report.turns[target_turn]
            reply = (str(turn.teach.teaching_block or "").strip() + "\n" + str(turn.teach.question or "").strip()).strip()
            reply_texts.append(reply)
            if not _normalize_reply(reply):
                empty_reply_count += 1

            teach_meta = turn.teach.prompt_meta if isinstance(turn.teach.prompt_meta, dict) else {}
            eval_meta = turn.eval.prompt_meta if isinstance(turn.eval.prompt_meta, dict) else {}
            mirror_meta = turn.mirror_meta if isinstance(turn.mirror_meta, dict) else {}
            sample_errors = _aggregate_errors(teach_meta, eval_meta, mirror_meta)
            mirror_error = str(mirror_meta.get("error") or "").strip() or None
            if sample_errors:
                backend_errors.append(sample_errors)
            if mirror_error:
                mirror_errors.append(mirror_error)

            teach_latency = int(teach_meta.get("tutor_latency_ms") or 0)
            eval_latency = int(eval_meta.get("tutor_latency_ms") or 0)
            mirror_latency = int(mirror_meta.get("latency_ms") or 0)
            lat = teach_latency + eval_latency + mirror_latency
            latencies.append(lat)
            samples.append(
                {
                    "seed": s,
                    "effective_seed": session_seed,
                    "seed_contract": seed_contract,
                    "turn_index": target_turn,
                    "session_turns": len(session_report.turns),
                    "reply_len": len(reply),
                    "reply_hash": _hash_text(reply),
                    "reply_non_empty": bool(_normalize_reply(reply)),
                    "teach_backend": teach_meta.get("tutor_backend"),
                    "eval_backend": eval_meta.get("tutor_backend"),
                    "mirror_backend": mirror_meta.get("backend"),
                    "mirror_prompt_mode": mirror_meta.get("prompt_mode") or _effective_mirror_prompt_mode(cfg),
                    "backend_error": sample_errors,
                    "mirror_error": mirror_error,
                    "latency_ms": lat,
                    "next_action": turn.eval.next_action,
                    "canonical_input_hash": _hash_text(canonical_input),
                    "enforce_determinism": bool(cfg.enforce_determinism),
                }
            )

        if not samples:
            print("INCOMPLETE: no samples generated")
            return 2

        unique_replies = len({_normalize_reply(r) for r in reply_texts})
        lengths = [s["reply_len"] for s in samples]
        mean_len = statistics.mean(lengths) if lengths else 0.0
        stdev_len = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0

        report = {
            "schema_version": "seed_sweep_report@1",
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "requested_seed": args.seed,
            "execution_mode": execution_mode,
            "enforce_determinism": bool(cfg.enforce_determinism),
            "seed_contract": seed_contract,
            "ambient_root_seed": ambient_root_seed,
            "turn_index": target_turn,
            "seed_range": {"start": args.seed_start, "end": args.seed_end},
            "input": args.text,
            "canonical_input": canonical_input,
            "canonical_input_hash": _hash_text(canonical_input),
            "mirror_send_user_content": bool(getattr(cfg, "mirror_send_user_content", False)),
            "mirror_prompt_mode": _effective_mirror_prompt_mode(cfg),
            "unique_replies": unique_replies,
            "empty_reply_count": empty_reply_count,
            "backend_error_count": len(backend_errors),
            "mirror_error_count": len(mirror_errors),
            "reply_length": {"mean": round(float(mean_len), 3), "stdev": round(float(stdev_len), 3)},
            "tutor_latency_ms": {"p95": _p95(latencies), "max": max(latencies) if latencies else 0},
            "samples": samples,
        }
        write_json(run_dir / "seed_sweep_report.json", report)

        summary = [
            "# Seed Sweep Summary",
            "",
            f"- issue: `{args.issue}`",
            f"- run_id: `{run_id}`",
            f"- execution_mode: `{execution_mode}`",
            f"- enforce_determinism: `{str(cfg.enforce_determinism).lower()}`",
            f"- seed_contract: `{seed_contract}`",
            f"- ambient_root_seed: `{ambient_root_seed}`",
            f"- seeds: `{args.seed_start}..{args.seed_end}`",
            f"- target_turn: `{target_turn}`",
            f"- mirror_send_user_content: `{str(bool(getattr(cfg, 'mirror_send_user_content', False))).lower()}`",
            f"- mirror_prompt_mode: `{_effective_mirror_prompt_mode(cfg)}`",
            f"- unique_replies: `{unique_replies}` (threshold `{args.max_unique_replies}`)",
            f"- empty_reply_count: `{empty_reply_count}`",
            f"- backend_error_count: `{len(backend_errors)}`",
            f"- mirror_error_count: `{len(mirror_errors)}`",
            f"- reply_len_mean: `{mean_len:.1f}` (stdev `{stdev_len:.1f}`)",
            f"- tutor_p95_latency_ms: `{_p95(latencies)}`",
            "",
        ]
        (run_dir / "seed_sweep_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

        run_meta = {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "requested_seed": args.seed,
            "execution_mode": execution_mode,
            "enforce_determinism": bool(cfg.enforce_determinism),
            "seed_contract": seed_contract,
            "ambient_root_seed": ambient_root_seed,
            "deterministic": bool(cfg.enforce_determinism),
            "canonical_input_hash": _hash_text(canonical_input),
            "mirror_send_user_content": bool(getattr(cfg, "mirror_send_user_content", False)),
            "mirror_prompt_mode": _effective_mirror_prompt_mode(cfg),
            "outputs": ["seed_sweep_report.json", "seed_sweep_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        }
        write_json(run_dir / "run.json", run_meta)

        ok = unique_replies <= args.max_unique_replies and empty_reply_count == 0
        print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
        return 0 if ok else 1
    except Exception as e:
        _cleanup_run_dir(run_dir)
        print(f"INCOMPLETE: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
