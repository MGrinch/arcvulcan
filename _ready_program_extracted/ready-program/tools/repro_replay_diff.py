#!/usr/bin/env python3
from __future__ import annotations
"""Repro replay + diff. Input: runs/<run_id>/{turn_report.json,session_report.json}. Exit codes: 0/1/2."""
import argparse
import html
import hashlib
import json
import os
import random
import sys
import unicodedata
from datetime import datetime
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
from xyzgl.router import route_turn
from xyzgl.knowledge.graph import SCHEMA_VERSION as KNOWLEDGE_GRAPH_SCHEMA_VERSION, default_graph
from xyzgl.orchestrator.session_loop import run_session
from witness.core import SCHEMA_VERSION as WITNESS_EVENT_SCHEMA_VERSION, WitnessCore

MAX_INPUT_JSON_BYTES = 8_000_000
MAX_HASH_JSON_BYTES = 2_000_000
MAX_ARTIFACT_INPUT_CHARS = 8_000


def _run_id() -> str:
    return make_run_id()


def _stable_hash(obj: object) -> str:
    h = hashlib.sha256()
    enc = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    normalized = _normalize_for_hash(obj)
    total = 0
    hashed = 0
    for chunk in enc.iterencode(normalized):
        b = chunk.encode("utf-8", errors="replace")
        total += len(b)
        if hashed < MAX_HASH_JSON_BYTES:
            remaining = MAX_HASH_JSON_BYTES - hashed
            take = min(len(b), remaining)
            h.update(b[:take])
            hashed += take
    if total > MAX_HASH_JSON_BYTES:
        h.update(f"...len={total}".encode("utf-8"))
    return h.hexdigest()[:16]


def _normalize_for_hash(v: object):
    if isinstance(v, str):
        return unicodedata.normalize("NFC", v).replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(v, list):
        return [_normalize_for_hash(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _normalize_for_hash(val) for k, val in v.items()}
    return v


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _extract_turn_result(doc: dict) -> dict | None:
    if not isinstance(doc, dict):
        return None
    schema = str(doc.get("schema_version") or "")
    if schema.startswith("turn_report"):
        return doc
    if all(k in doc for k in ("config", "input", "reply", "backend")):
        return doc
    payload = doc.get("payload") or {}
    v = payload.get("turn_result")
    return v if isinstance(v, dict) else None


def _extract_session_report(doc: dict) -> dict | None:
    if not isinstance(doc, dict):
        return None
    schema = str(doc.get("schema_version") or "")
    if schema == "session_report@1":
        return doc
    payload = doc.get("payload") or {}
    v = payload.get("session_report")
    return v if isinstance(v, dict) else None


def _is_within(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _truncate_text(value: object, *, max_chars: int) -> str:
    text = str(value or "")
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load_json(path: Path) -> dict:
    try:
        if int(path.stat().st_size) > MAX_INPUT_JSON_BYTES:
            return {}
    except OSError:
        return {}
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}




def _load_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _normalize_text(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")


def _extract_fenced_markdown_section(markdown: str, heading: str) -> str | None:
    lines = _normalize_text(markdown).split("\n")
    target_heading = heading.strip()
    i = 0
    while i < len(lines):
        if lines[i].strip() != target_heading:
            i += 1
            continue
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines) or not lines[i].lstrip().startswith("```"):
            return None
        i += 1
        buf: list[str] = []
        while i < len(lines) and not lines[i].lstrip().startswith("```"):
            buf.append(lines[i])
            i += 1
        if i >= len(lines):
            return None
        value = "\n".join(buf)
        return html.unescape(value).replace("``\\`", "```")
    return None


def _extract_turn_summary_input(markdown: str) -> tuple[str | None, str | None]:
    for heading in ("## Routed Input", "## Input", "## Raw CLI Input"):
        value = _extract_fenced_markdown_section(markdown, heading)
        if value is not None:
            return heading, value
    return None, None


def _extract_issue_id_markdown_value(markdown: str) -> str | None:
    for raw_line in _normalize_text(markdown).split("\n"):
        normalized = raw_line.strip().lstrip("-* ").strip()
        if not normalized.lower().startswith("issue:"):
            continue
        value = normalized.split(":", 1)[1].strip()
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            value = value[1:-1].strip()
        return value or None
    return None


def _crosscheck_turn_bundle_issue_identity(
    path: Path,
    *,
    issue: str,
    doc: dict,
    tr: dict,
    summary_text: str | None,
) -> tuple[list[str], dict]:
    observed_issue_ids: dict[str, str] = {"cli": issue}

    run_path = path.with_name("run.json")
    if run_path.exists():
        run_doc = _load_json(run_path)
        run_issue = str(run_doc.get("issue_id") or "").strip()
        if run_issue:
            observed_issue_ids["run.json"] = run_issue

    witness_issue = str(doc.get("issue_id") or "").strip()
    if witness_issue:
        observed_issue_ids["turn_report.json.witness.issue_id"] = witness_issue

    nested_turn_issue = str(tr.get("issue_id") or "").strip()
    if nested_turn_issue:
        observed_issue_ids["turn_report.json.payload.turn_result.issue_id"] = nested_turn_issue

    if summary_text is not None:
        summary_issue = _extract_issue_id_markdown_value(summary_text)
        if summary_issue:
            observed_issue_ids["turn_summary.md"] = summary_issue

    if len(observed_issue_ids) <= 1:
        return [], {}

    problems = [
        f"{source}: issue_id mismatch: expected {issue} got {actual_issue}"
        for source, actual_issue in observed_issue_ids.items()
        if source != "cli" and actual_issue != issue
    ]
    diff = {
        "expected_issue_id": issue,
        "observed_issue_ids": observed_issue_ids,
        "unique_issue_ids": sorted(set(observed_issue_ids.values())),
    }
    return problems, diff


def _compact_value(v: object):
    if isinstance(v, str):
        s = v
        return {
            "type": "str",
            "len": len(s),
            "sha256": _stable_hash(s),
            "preview": s[:400],
        }
    if isinstance(v, list):
        return {
            "type": "list",
            "len": len(v),
            "sha256": _stable_hash(v),
        }
    if isinstance(v, dict):
        keys = sorted(str(k) for k in v.keys())
        return {
            "type": "dict",
            "len": len(v),
            "keys_sample": keys[:40],
            "sha256": _stable_hash(v),
        }
    return {"type": type(v).__name__, "repr": repr(v)[:200], "sha256": _stable_hash(v)}


def _recognized_config_dict(cfg_dict: object) -> dict:
    if not isinstance(cfg_dict, dict):
        return {}
    allowed = XYZGLConfig.__dataclass_fields__
    return {k: v for k, v in cfg_dict.items() if k in allowed}


def _is_canonical_witness_created_at(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return False
    if dt.utcoffset() is None or int(dt.utcoffset().total_seconds()) != 0:
        return False
    return value == dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _strict_turn_envelope_expected(payload: object, *, issue: str) -> dict:
    expected_event_id = None
    expected_created_at = None
    if isinstance(payload, dict):
        event = WitnessCore().make_event(issue, payload)
        expected_event_id = event.event_id
        expected_created_at = event.created_at
    return {
        "schema_version": WITNESS_EVENT_SCHEMA_VERSION,
        "issue_id": issue,
        "event_id": expected_event_id,
        "created_at": expected_created_at,
    }


def _strict_turn_envelope_actual(doc: dict) -> dict:
    return {
        "schema_version": doc.get("schema_version"),
        "issue_id": doc.get("issue_id"),
        "event_id": doc.get("event_id"),
        "created_at": doc.get("created_at"),
    }


def _is_turn_witness_wrapper(doc: dict) -> bool:
    payload = doc.get("payload")
    return isinstance(payload, dict) and isinstance(payload.get("turn_result"), dict)


def _strict_turn_envelope_problems(doc: dict, *, issue: str) -> list[str]:
    problems: list[str] = []
    payload = doc.get("payload")
    expected = _strict_turn_envelope_expected(payload, issue=issue)
    actual = _strict_turn_envelope_actual(doc)
    if actual.get("schema_version") != expected.get("schema_version"):
        problems.append(
            f"mismatch witness.schema_version: expected {_stable_hash(expected.get('schema_version'))} got {_stable_hash(actual.get('schema_version'))}"
        )
    if actual.get("issue_id") != expected.get("issue_id"):
        problems.append(
            f"mismatch witness.issue_id: expected {_stable_hash(expected.get('issue_id'))} got {_stable_hash(actual.get('issue_id'))}"
        )
    expected_event_id = expected.get("event_id")
    if expected_event_id is None:
        problems.append("cannot validate witness.event_id from non-object payload")
    elif actual.get("event_id") != expected_event_id:
        problems.append(
            f"mismatch witness.event_id: expected {_stable_hash(expected_event_id)} got {_stable_hash(actual.get('event_id'))}"
        )
    expected_created_at = expected.get("created_at")
    actual_created_at = actual.get("created_at")
    if expected_created_at is None:
        problems.append("cannot validate witness.created_at from non-object payload")
    elif actual_created_at != expected_created_at:
        problems.append(
            f"mismatch witness.created_at: expected {_stable_hash(expected_created_at)} got {_stable_hash(actual_created_at)}"
        )
    elif not _is_canonical_witness_created_at(actual_created_at):
        problems.append("mismatch witness.created_at: expected canonical UTC seconds timestamp")
    return problems


def _knowledge_graph_to_json(graph: object) -> dict:
    raw_nodes = getattr(graph, "nodes", None) or []
    nodes_out: list[dict] = []
    for n in raw_nodes:
        raw_confidence = getattr(n, "confidence", 0.0)
        raw_last_verified_turn = getattr(n, "last_verified_turn", -1)
        nodes_out.append({
            "node_id": str(getattr(n, "node_id", "") or ""),
            "title": str(getattr(n, "title", "") or ""),
            "summary": str(getattr(n, "summary", "") or ""),
            "required_keywords": [str(v or "") for v in list(getattr(n, "required_keywords", []) or [])],
            "confidence": float(raw_confidence if raw_confidence is not None else 0.0),
            "fragility_flags": [str(v or "") for v in list(getattr(n, "fragility_flags", []) or [])],
            "last_verified_turn": int(raw_last_verified_turn if raw_last_verified_turn is not None else -1),
        })
    nodes_out.sort(key=lambda item: item.get("node_id") or "")
    return {"schema_version": KNOWLEDGE_GRAPH_SCHEMA_VERSION, "nodes": nodes_out}


def _sim_user_answer(node_id: str, required: list[str], *, seed: int) -> str:
    digest = hashlib.sha256((node_id or "").encode("utf-8")).hexdigest()
    salt = int(digest[:8], 16) % 10_000
    r = random.Random(seed + salt)
    base = " ".join([kw for kw in (required or []) if kw])
    filler = ["because", "so", "that", "means", "you", "need", "to"]
    r.shuffle(filler)
    return f"I think {base} {filler[0]} {filler[1]} {filler[2]}.".strip()


def _parse_session_prompt(prompt: str) -> tuple[str, str]:
    lines = (prompt or "").splitlines()
    node_id_from_prompt = ""
    title = ""
    for ln in lines[:4]:
        low = ln.strip().lower()
        if low.startswith("node_id:"):
            node_id_from_prompt = ln.split(":", 1)[1].strip()
        elif low.startswith("node:"):
            title = ln.split(":", 1)[1].strip()
    return node_id_from_prompt, title


def _replay_session(sr: dict, *, seed: int) -> tuple[dict, dict]:
    turns = sr.get("turns") or []
    raw_max_turns = sr.get("max_turns")
    max_turns = _safe_int(raw_max_turns, default=int(len(turns))) if raw_max_turns is not None else int(len(turns))
    mirror_enabled = any(((t.get("mirror") or {}).get("answer") is not None) for t in turns)

    regrounded = [
        _safe_int(t.get("turn_index"), 0)
        for t in turns
        if bool(((t.get("teach") or {}).get("prompt_meta") or {}).get("protocol_regrounded"))
    ]
    every = 5
    if len(regrounded) >= 2:
        diffs = [b - a for a, b in zip(regrounded, regrounded[1:]) if b - a > 0]
        if diffs:
            every = min(diffs)

    grounding_enabled = any(bool(((t.get("teach") or {}).get("prompt_meta") or {}).get("grounding_enabled")) for t in turns)
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=bool(mirror_enabled),
        protocol_reground_every=int(every),
        grounding_mode="local" if grounding_enabled else "off",
    )

    graph = default_graph()
    recorded_answers = [str(((t.get("eval") or {}).get("user_answer")) or "") for t in turns]
    answer_index = 0

    def input_provider(prompt: str):
        nonlocal answer_index
        if answer_index < len(recorded_answers):
            answer = recorded_answers[answer_index]
            answer_index += 1
            return answer, {"typing_ms": 4500}

        node_id_from_prompt, title = _parse_session_prompt(prompt)
        node_id, required = "unknown", []
        if node_id_from_prompt:
            n = graph.get(node_id_from_prompt)
            if n is not None:
                node_id, required = n.node_id, n.required_keywords
        if not required:
            for n in graph.nodes:
                if n.title == title:
                    node_id, required = n.node_id, n.required_keywords
                    break
        return _sim_user_answer(node_id, required, seed=seed), {"typing_ms": 4500}

    session_report, graph2 = run_session(
        session_id=str(sr.get("session_id") or "replay"),
        cfg=cfg,
        seed=seed,
        max_turns=max_turns,
        graph=graph,
        input_provider=input_provider,
    )
    return session_report.to_json(), _knowledge_graph_to_json(graph2)


def _write_bundle(out_dir: Path, *, run_id: str, issue: str, seed: int | None, overall: str) -> None:
    write_json(
        (out_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": issue,
            "seed": seed,
            "deterministic": True,
            "outputs": ["replay_diff_report.json", "replay_diff_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )
    (out_dir / "replay_diff_summary.md").write_text(
        "\n".join([f"# Replay Diff Summary — {overall}", "", f"- issue: {issue}", f"- run_id: {run_id}", ""]),
        encoding="utf-8",
    )


def _merge_status(current: tuple[str, int], incoming: tuple[str, int]) -> tuple[str, int]:
    rank = {"PASS": 0, "INCOMPLETE": 1, "FAIL": 2}
    return incoming if rank.get(incoming[0], -1) > rank.get(current[0], -1) else current


def _normalized_session_turns_for_compare(turns: object) -> object:
    if not isinstance(turns, list):
        return turns
    normalized_turns: list[object] = []
    for turn in turns:
        if not isinstance(turn, dict):
            normalized_turns.append(turn)
            continue
        turn_out = dict(turn)
        turn_out.pop("telemetry", None)
        teach = dict(turn_out.get("teach") or {})
        eval_block = dict(turn_out.get("eval") or {})
        for key in ("teaching_block", "question"):
            if teach.get(key) is None:
                teach[key] = ""
            elif not isinstance(teach.get(key), str):
                teach[key] = str(teach.get(key))
        for key in ("user_answer", "evaluation", "gaps", "next_action", "next_question"):
            if eval_block.get(key) is None:
                eval_block[key] = ""
            elif not isinstance(eval_block.get(key), str):
                eval_block[key] = str(eval_block.get(key))
        turn_out["teach"] = teach
        turn_out["eval"] = eval_block
        normalized_turns.append(turn_out)
    return normalized_turns


def _extract_inline_code_value(line: str) -> str | None:
    stripped = line.strip()
    if len(stripped) < 2 or not stripped.startswith("`") or not stripped.endswith("`"):
        return None
    return stripped[1:-1]


def _extract_labeled_summary_value(markdown: str, label: str) -> str | None:
    lines = _normalize_text(markdown).split("\n")
    target = f"**{label}:**"
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith(target):
            i += 1
            continue
        remainder = line[len(target) :].lstrip()
        if remainder.startswith("```"):
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            if i >= len(lines):
                return None
            return html.unescape("\n".join(buf)).replace("``\\`", "```")
        inline_code = _extract_inline_code_value(remainder)
        if inline_code is not None:
            return inline_code
        return remainder.strip()
    return None


def _session_summary_crosscheck(sr: dict, summary_text: str) -> tuple[list[str], dict]:
    problems: list[str] = []
    diff: dict = {}
    turns = sr.get("turns")
    if not isinstance(turns, list) or not turns:
        return problems, diff

    last = turns[-1] if isinstance(turns[-1], dict) else {}
    teach = last.get("teach") if isinstance(last, dict) else {}
    eval_block = last.get("eval") if isinstance(last, dict) else {}
    if not isinstance(teach, dict):
        teach = {}
    if not isinstance(eval_block, dict):
        eval_block = {}

    expected_values = {
        "node_title": _normalize_text(last.get("node_title")),
        "tutor_state": _normalize_text(teach.get("user_state")),
        "post_eval_state": _normalize_text(eval_block.get("inferred_user_state") or last.get("user_state")),
        "tutor_question": _normalize_text(teach.get("question")),
        "user_answer": _normalize_text(eval_block.get("user_answer")),
    }
    actual_values = {
        "node_title": _normalize_text(_extract_labeled_summary_value(summary_text, "Node")),
        "tutor_state": _normalize_text(_extract_labeled_summary_value(summary_text, "Tutor State")),
        "post_eval_state": _normalize_text(_extract_labeled_summary_value(summary_text, "Post-Eval State")),
        "tutor_question": _normalize_text(_extract_labeled_summary_value(summary_text, "Tutor Question")),
        "user_answer": _normalize_text(_extract_labeled_summary_value(summary_text, "User Answer")),
    }

    for key in expected_values:
        if expected_values[key] != actual_values[key]:
            problems.append(
                f"session_summary.md: mismatch {key}: expected {_stable_hash(expected_values[key])} got {_stable_hash(actual_values[key])}"
            )

    diff = {
        "expected": {k: _compact_value(v) for k, v in expected_values.items()},
        "actual": {k: _compact_value(v) for k, v in actual_values.items()},
    }
    return problems, diff


def _check_turn_report(path: Path, *, strict: bool, issue: str) -> tuple[tuple[str, int], list[str], dict, int | None]:
    problems: list[str] = []
    diff: dict = {}
    seed_out: int | None = None
    doc = _load_json(path)
    tr = _extract_turn_result(doc)
    if tr is None:
        return ("FAIL", 1), ["turn_report.json: cannot extract payload.turn_result"], diff, seed_out

    summary_diff: dict = {}
    issue_diff: dict = {}
    summary_path = path.with_name("turn_summary.md")
    summary_text: str | None = None
    if summary_path.exists():
        summary_text = _load_text(summary_path)
        summary_heading, summary_input = _extract_turn_summary_input(summary_text)
        if summary_input is None:
            problems.append("turn_summary.md: missing parseable routed input fenced block")
        else:
            expected_input = _normalize_text(tr.get("input"))
            expected_summary_input = _truncate_text(expected_input, max_chars=MAX_ARTIFACT_INPUT_CHARS)
            summary_input_normalized = _normalize_text(summary_input)
            summary_diff = {
                "turn_summary_heading": summary_heading,
                "turn_report_input": _compact_value(expected_input),
                "expected_turn_summary_input": _compact_value(expected_summary_input),
                "turn_summary_input": _compact_value(summary_input_normalized),
            }
            if summary_input_normalized != expected_summary_input:
                problems.append(
                    f"turn_summary.md: input mismatch: expected {_stable_hash(expected_summary_input)} got {_stable_hash(summary_input_normalized)}"
                )

    issue_problems, issue_diff = _crosscheck_turn_bundle_issue_identity(
        path,
        issue=issue,
        doc=doc,
        tr=tr,
        summary_text=summary_text,
    )
    problems.extend(issue_problems)

    raw_cfg_dict = tr.get("config") or {}
    effective_cfg_dict = _recognized_config_dict(raw_cfg_dict)
    raw_seed = tr.get("seed")
    seed_out = 1337 if raw_seed is None else _safe_int(raw_seed, 1337)
    if str(effective_cfg_dict.get("tutor_backend")) not in {"stub", "fault"}:
        return ("INCOMPLETE", 2), ["turn_report.json: non-stub backend; replay not deterministic"], diff, seed_out

    cfg = XYZGLConfig(**effective_cfg_dict)
    raw_turn_index = tr.get("turn_index")
    turn_index = 0 if raw_turn_index is None else _safe_int(raw_turn_index, 0)
    out = route_turn(tr.get("input") or "", seed=seed_out, cfg=cfg, turn_index=turn_index)

    expected_values = {
        "reply": tr.get("reply"),
        "backend": tr.get("backend"),
        "prompt_meta": tr.get("prompt_meta"),
    }
    replayed_values = {
        "reply": out.get("reply"),
        "backend": out.get("backend"),
        "prompt_meta": out.get("prompt_meta"),
    }

    if strict:
        expected_values.update({
            "config": effective_cfg_dict,
            "turn_index": raw_turn_index,
            "mirror_prediction": tr.get("mirror_prediction"),
            "mirror_meta": tr.get("mirror_meta"),
            "backend_error": tr.get("backend_error"),
            "requested_backend": tr.get("requested_backend"),
            "effective_backend": tr.get("effective_backend"),
            "tutor_meta": tr.get("tutor_meta"),
        })
        replayed_values.update({
            "config": _recognized_config_dict(out.get("config")),
            "turn_index": out.get("turn_index"),
            "mirror_prediction": out.get("mirror_prediction"),
            "mirror_meta": out.get("mirror_meta"),
            "backend_error": out.get("backend_error"),
            "requested_backend": out.get("requested_backend"),
            "effective_backend": out.get("effective_backend"),
            "tutor_meta": out.get("tutor_meta"),
        })
        if _is_turn_witness_wrapper(doc):
            expected_values["witness_envelope"] = _strict_turn_envelope_expected(doc.get("payload"), issue=issue)
            replayed_values["witness_envelope"] = _strict_turn_envelope_actual(doc)
            problems.extend(_strict_turn_envelope_problems(doc, issue=issue))

    keys = list(expected_values.keys())
    for k in keys:
        if expected_values.get(k) != replayed_values.get(k):
            problems.append(
                f"turn_report.json: mismatch {k}: expected {_stable_hash(expected_values.get(k))} got {_stable_hash(replayed_values.get(k))}"
            )
    status = ("FAIL", 1) if problems else ("PASS", 0)
    diff = {
        "expected": {k: _compact_value(expected_values.get(k)) for k in keys},
        "replayed": {k: _compact_value(replayed_values.get(k)) for k in keys},
    }
    bundle_crosscheck: dict = {}
    if summary_diff:
        bundle_crosscheck.update(summary_diff)
    if issue_diff:
        bundle_crosscheck["issue_identities"] = issue_diff
    if bundle_crosscheck:
        diff["bundle_crosscheck"] = bundle_crosscheck
    return status, problems, diff, seed_out


def _check_session_report(path: Path) -> tuple[tuple[str, int], list[str], dict, int | None]:
    problems: list[str] = []
    diff: dict = {}
    seed_out: int | None = None
    doc = _load_json(path)
    sr = _extract_session_report(doc)
    if sr is None:
        return ("FAIL", 1), ["session_report.json: cannot extract payload.session_report"], diff, seed_out

    raw_seed = sr.get("seed")
    seed_out = 1337 if raw_seed is None else _safe_int(raw_seed, 1337)
    replayed, replayed_graph = _replay_session(sr, seed=seed_out)
    expected_turns = _normalized_session_turns_for_compare(sr.get("turns"))
    replayed_turns = _normalized_session_turns_for_compare(replayed.get("turns"))
    if _stable_hash(replayed_turns) != _stable_hash(expected_turns):
        problems.append("session_report.json: turns mismatch")

    bundle_crosscheck: dict = {}
    kg_path = path.with_name("knowledge_graph.json")
    if kg_path.exists():
        stored_graph = _load_json(kg_path)
        bundle_crosscheck.update({
            "knowledge_graph_expected": _compact_value(stored_graph),
            "knowledge_graph_replayed": _compact_value(replayed_graph),
        })
        if _stable_hash(stored_graph) != _stable_hash(replayed_graph):
            problems.append(
                f"knowledge_graph.json: mismatch: expected {_stable_hash(stored_graph)} got {_stable_hash(replayed_graph)}"
            )

    summary_path = path.with_name("session_summary.md")
    if summary_path.exists():
        summary_problems, summary_diff = _session_summary_crosscheck(sr, _load_text(summary_path))
        problems.extend(summary_problems)
        if summary_diff:
            bundle_crosscheck["session_summary"] = summary_diff

    status = ("FAIL", 1) if problems else ("PASS", 0)
    diff = {"expected_hash": _stable_hash(expected_turns), "replayed_hash": _stable_hash(replayed_turns)}
    if bundle_crosscheck:
        diff["bundle_crosscheck"] = bundle_crosscheck
    return status, problems, diff, seed_out


def main() -> int:
    ap = argparse.ArgumentParser(prog="repro_replay_diff")
    ap.add_argument("path", help="runs/<run_id>/ dir")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--strict", action="store_true", help="Compare more fields")
    ap.add_argument(
        "--allow-external-path",
        action="store_true",
        help="Allow replay source path outside repo root.",
    )
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    target = Path(args.path).resolve()
    if not target.exists() or not target.is_dir():
        print(f"FAIL: not a dir: {target}")
        return 1
    if not args.allow_external_path and not _is_within(_REPO_ROOT, target):
        print("INCOMPLETE: path must be within repo root unless --allow-external-path is set")
        return 2

    random.seed(1337)
    run_id = _run_id()
    out_dir = allocate_run_dir(run_id)
    turn_path = target / "turn_report.json"
    session_path = target / "session_report.json"

    overall, exit_code = "PASS", 0
    problems: list[str] = []
    diff: dict = {}
    seed_out: int | None = None
    found_any = False

    if turn_path.exists():
        found_any = True
        status, turn_problems, turn_diff, turn_seed = _check_turn_report(turn_path, strict=args.strict, issue=args.issue)
        overall, exit_code = _merge_status((overall, exit_code), status)
        problems.extend(turn_problems)
        diff = turn_diff if not diff else {**diff, "turn_report": turn_diff}
        if seed_out is None:
            seed_out = turn_seed

    if session_path.exists():
        found_any = True
        status, session_problems, session_diff, session_seed = _check_session_report(session_path)
        overall, exit_code = _merge_status((overall, exit_code), status)
        problems.extend(session_problems)
        if diff:
            if "turn_report" in diff or "session_report" in diff:
                diff["session_report"] = session_diff
            else:
                diff = {"turn_report": diff, "session_report": session_diff}
        else:
            diff = session_diff
        if seed_out is None:
            seed_out = session_seed

    if not found_any:
        overall, exit_code = "INCOMPLETE", 2
        problems.append("no turn_report.json or session_report.json found")

    report = {
        "schema_version": "replay_diff_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "source": str(target),
        "overall": overall,
        "problems": problems,
        "diff": diff,
    }
    write_json((out_dir / "replay_diff_report.json"), report)
    _write_bundle(out_dir, run_id=run_id, issue=args.issue, seed=seed_out, overall=overall)

    print(f"{overall}: wrote outputs to {out_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
