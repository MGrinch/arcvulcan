#!/usr/bin/env python3
from __future__ import annotations

"""Mirror leakage detector.

The Mirror backend must simulate the learner, not teach. This tool scans
mirror outputs in session_report.json for common teaching/imperative patterns
("you should", "make sure", etc.).

Exit codes:
  0 PASS
  1 FAIL (found role leakage)
  2 INCOMPLETE (no mirror answers present or malformed input)
"""

import argparse
import hashlib
import html
import json
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id


def _run_id() -> str:
    return make_run_id()


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


_PATTERN_DEFS = [
    ("you should", r"\byou should\b"),
    ("make sure", r"\bmake sure\b"),
    ("remember to", r"\bremember to\b"),
    ("you need/must/should", r"\byou (?:need|must|should)\b"),
    ("please + directive", r"\bplease (?:try|remember|make sure|consider|start)\b"),
    ("be sure to", r"\bbe sure to\b"),
    ("the key is to", r"\bthe key is to\b"),
    ("good place to start", r"\ba good place to start is to\b"),
    ("one place to start", r"\bone place to start is to\b"),
    ("helpful place to begin", r"\ba helpful place to begin is to\b"),
    ("good idea to", r"\bit would be a good idea to\b"),
    ("you'd be wise to", r"\byou(?:'d| would)? be wise to\b"),
    ("my first move would be", r"\bmy first move would be\b"),
    ("it makes sense to", r"\bit makes sense to\b"),
    ("why not", r"\bwhy not\b"),
    ("can you", r"^\s*(?:q\s*:\s*)?can you\b"),
    ("would you", r"^\s*(?:q\s*:\s*)?would you\b"),
    ("have you tried", r"^\s*(?:q\s*:\s*)?have you tried\b"),
    ("as your tutor", r"\bas your tutor\b"),
    ("today's lesson", r"\b(?:in\s+)?today'?s lesson\b"),
    ("let's learn/practice", r"\blet'?s (?:learn|practice|start)\b"),
    ("i recommend/suggest", r"\bi (?:recommend|suggest)\b"),
    ("numbered step", r"^\s*(?:step\s*)?\d+[.)]\s+[A-Za-z]"),
    ("spanish coaching", r"\b(?:deber[ií]as|aseg[uú]rate de|recuerda(?:\s+que)?|por qu[eé] no|como tu tutor)\b"),
    ("japanese coaching", r"(?:まずは|今日のレッスン|してみましょう|してください)"),
]
_RES = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in _PATTERN_DEFS]
MAX_INPUT_JSON_BYTES = 8_000_000
_ABS_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9_.-])(?:[A-Z]:\\|/)[^\s]+")
_MARKUP_RE = re.compile(r"<[^>]+>|[`*_~]+")
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
    }
)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _redacted_excerpt(text: str) -> str:
    t = str(text or "")
    digest = hashlib.sha256(t.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"<redacted len={len(t)} sha256={digest}>"


def _extract_embedded_issue_id(doc: object) -> str | None:
    if not isinstance(doc, dict):
        return None

    direct = str(doc.get("issue_id") or "").strip()
    if direct:
        return direct

    payload = doc.get("payload")
    if isinstance(payload, dict):
        payload_issue = str(payload.get("issue_id") or "").strip()
        if payload_issue:
            return payload_issue
        sr = payload.get("session_report")
        if isinstance(sr, dict):
            nested = str(sr.get("issue_id") or "").strip()
            if nested:
                return nested

    nested = str(doc.get("issue_id") or "").strip()
    return nested or None


def _display_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(_REPO_ROOT.resolve())
        s = str(rel).replace("\\", "/")
        if s and s != ".":
            return s
    except Exception:
        pass
    name = path.name.strip()
    return name or "<path>"


def _sanitize_text(text: object) -> str:
    return _ABS_PATH_RE.sub("<path>", str(text or ""))


def _normalize_scan_text(value: str) -> str:
    text = html.unescape(value)
    text = unicodedata.normalize("NFKC", text).translate(_CONFUSABLES)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = _MARKUP_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _scan_text(raw_text: str) -> str | None:
    text = _normalize_scan_text(raw_text)
    if not text:
        return None
    for label, rx in _RES:
        if rx.search(text):
            return label
    if _looks_like_imperative_coaching(text):
        return "imperative coaching"
    return None


_IMPERATIVE_SENTENCE_RE = re.compile(
    r"^\s*(?:q\s*:\s*)?(?:please\s+)?(?:stop|start|begin|try|check|review|remember|keep|make|focus|look|grind|re-?tack|explain|describe|list|show|write|practice|compare)\b",
    re.I,
)



def _looks_like_imperative_coaching(text: str) -> bool:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    imperative_hits = 0
    for sentence in sentences[:6]:
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", sentence)
        if _IMPERATIVE_SENTENCE_RE.search(cleaned):
            imperative_hits += 1
            if imperative_hits >= 2:
                return True
    return False


def _append_finding(findings: list[dict], *, turn_index: int, node_id: str, field: str, pattern: str, raw_text: object):
    if isinstance(raw_text, str):
        excerpt = _redacted_excerpt(raw_text)
    else:
        excerpt = f"<non-string type={type(raw_text).__name__}>"
    findings.append(
        {
            "turn_index": turn_index,
            "node_id": node_id,
            "field": field,
            "pattern": pattern,
            "excerpt": excerpt,
        }
    )


def _append_problem(problems: list[dict], *, turn_index: int | None, node_id: str | None, field: str, detail: str):
    item = {"field": field, "detail": detail}
    if turn_index is not None:
        item["turn_index"] = turn_index
    if node_id:
        item["node_id"] = node_id
    problems.append(item)


def _scan_mirror_field(findings: list[dict], *, turn_index: int, node_id: str, field: str, raw_text: object) -> bool:
    if raw_text is None:
        return False
    if not isinstance(raw_text, str):
        _append_finding(
            findings,
            turn_index=turn_index,
            node_id=node_id,
            field=field,
            pattern="non-string mirror answer",
            raw_text=raw_text,
        )
        return True

    if not raw_text.strip():
        return False

    pattern = _scan_text(raw_text)
    if pattern:
        _append_finding(
            findings,
            turn_index=turn_index,
            node_id=node_id,
            field=field,
            pattern=pattern,
            raw_text=raw_text,
        )
    return True


def _extract_session_report(raw_doc: object) -> tuple[dict | None, list[dict]]:
    problems: list[dict] = []
    if not isinstance(raw_doc, dict):
        _append_problem(problems, turn_index=None, node_id=None, field="root", detail="root must be object")
        return None, problems

    schema = str(raw_doc.get("schema_version") or "").strip()
    session_doc: object | None = None

    if schema == "session_report@1":
        session_doc = raw_doc
    else:
        has_payload = "payload" in raw_doc
        payload = raw_doc.get("payload") if has_payload else None
        if has_payload:
            if not isinstance(payload, dict):
                _append_problem(problems, turn_index=None, node_id=None, field="payload", detail="payload must be object")
                return None, problems
            if "session_report" not in payload:
                _append_problem(
                    problems,
                    turn_index=None,
                    node_id=None,
                    field="payload.session_report",
                    detail="missing session_report object",
                )
                return None, problems
            session_doc = payload.get("session_report")
            if not isinstance(session_doc, dict):
                _append_problem(
                    problems,
                    turn_index=None,
                    node_id=None,
                    field="payload.session_report",
                    detail="session_report must be object",
                )
                return None, problems
        else:
            _append_problem(
                problems,
                turn_index=None,
                node_id=None,
                field="root",
                detail="unrecognized report/session shape",
            )
            return None, problems

    if not isinstance(session_doc, dict):
        _append_problem(problems, turn_index=None, node_id=None, field="session_report", detail="session_report must be object")
        return None, problems

    inner_schema = str(session_doc.get("schema_version") or "").strip()
    if inner_schema != "session_report@1":
        _append_problem(
            problems,
            turn_index=None,
            node_id=None,
            field="session_report.schema_version",
            detail="expected session_report@1",
        )

    session_id = session_doc.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        _append_problem(
            problems,
            turn_index=None,
            node_id=None,
            field="session_report.session_id",
            detail="session_id must be non-empty string",
        )

    max_turns = session_doc.get("max_turns")
    if not _is_strict_int(max_turns) or int(max_turns) < 1:
        _append_problem(
            problems,
            turn_index=None,
            node_id=None,
            field="session_report.max_turns",
            detail="max_turns must be integer >= 1",
        )
        max_turns = None

    turns = session_doc.get("turns")
    if not isinstance(turns, list):
        _append_problem(problems, turn_index=None, node_id=None, field="session_report.turns", detail="turns must be list")
    else:
        for idx, turn in enumerate(turns):
            if not isinstance(turn, dict):
                _append_problem(problems, turn_index=idx, node_id=None, field="turn", detail="turn must be object")
                continue

            raw_turn_index = turn.get("turn_index")
            node_id = turn.get("node_id") if isinstance(turn.get("node_id"), str) else None
            if not _is_strict_int(raw_turn_index) or int(raw_turn_index) < 0:
                _append_problem(
                    problems,
                    turn_index=idx,
                    node_id=node_id,
                    field="turn_index",
                    detail="turn_index must be integer >= 0",
                )
            elif max_turns is not None and int(raw_turn_index) >= int(max_turns):
                _append_problem(
                    problems,
                    turn_index=int(raw_turn_index),
                    node_id=node_id,
                    field="turn_index",
                    detail="turn_index must be less than max_turns",
                )

            if not isinstance(turn.get("node_id"), str) or not str(turn.get("node_id")).strip():
                _append_problem(problems, turn_index=idx, node_id=None, field="node_id", detail="node_id must be non-empty string")

            if "node_title" in turn and turn.get("node_title") is not None and not isinstance(turn.get("node_title"), str):
                _append_problem(problems, turn_index=idx, node_id=node_id, field="node_title", detail="node_title must be string")
            if "user_state" in turn and turn.get("user_state") is not None and not isinstance(turn.get("user_state"), str):
                _append_problem(problems, turn_index=idx, node_id=node_id, field="user_state", detail="user_state must be string")
            if "teach" in turn and turn.get("teach") is not None and not isinstance(turn.get("teach"), dict):
                _append_problem(problems, turn_index=idx, node_id=node_id, field="teach", detail="teach must be object")
            if not isinstance(turn.get("mirror"), dict):
                _append_problem(problems, turn_index=idx, node_id=node_id, field="mirror", detail="mirror must be object")
            if not isinstance(turn.get("eval"), dict):
                _append_problem(problems, turn_index=idx, node_id=node_id, field="eval", detail="eval must be object")

    if problems:
        return None, problems
    return session_doc, problems


def main() -> int:
    p = argparse.ArgumentParser(prog="mirror_leakage_detector")
    p.add_argument("path", help="session_report.json or runs/<run_id>/ dir")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    target = Path(args.path)
    fp = (target / "session_report.json") if target.is_dir() else target
    input_display = _display_path(fp)
    if not fp.exists():
        print(f"FAIL: not found: {input_display}")
        return 1
    try:
        if int(fp.stat().st_size) > MAX_INPUT_JSON_BYTES:
            print(f"INCOMPLETE: input too large: {input_display}")
            return 2
    except OSError:
        print(f"INCOMPLETE: cannot stat input: {input_display}")
        return 2

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    output_display = _display_path(run_dir)

    try:
        raw_doc = json.loads(fp.read_text(encoding="utf-8", errors="replace"), object_pairs_hook=_no_duplicate_pairs)
    except Exception as e:
        print(f"INCOMPLETE: invalid JSON input: {e}")
        return 2

    embedded_issue_id = _extract_embedded_issue_id(raw_doc)
    issue_mismatch = bool(embedded_issue_id and embedded_issue_id != args.issue)

    doc, input_problems = _extract_session_report(raw_doc)
    turns = (doc.get("turns") or []) if isinstance(doc, dict) else []

    findings: list[dict] = []
    problems: list[dict] = list(input_problems)
    saw_any = False
    for idx, t in enumerate(turns):
        if not isinstance(t, dict):
            _append_problem(problems, turn_index=idx, node_id=None, field="turn", detail="turn must be object")
            continue

        td = t
        tid = td.get("turn_index") if _is_strict_int(td.get("turn_index")) else idx
        node_id = str(td.get("node_id") or "")

        if "mirror" in td and td.get("mirror") is not None and not isinstance(td.get("mirror"), dict):
            _append_problem(problems, turn_index=tid, node_id=node_id, field="mirror", detail="mirror must be object")
            continue

        if "eval" in td and td.get("eval") is not None and not isinstance(td.get("eval"), dict):
            _append_problem(problems, turn_index=tid, node_id=node_id, field="eval", detail="eval must be object")
            continue

        mirror = _as_dict(td.get("mirror")).get("answer")
        eval_mirror = _as_dict(td.get("eval")).get("mirror_answer")
        saw_any = _scan_mirror_field(findings, turn_index=tid, node_id=node_id, field="mirror.answer", raw_text=mirror) or saw_any
        saw_any = _scan_mirror_field(findings, turn_index=tid, node_id=node_id, field="eval.mirror_answer", raw_text=eval_mirror) or saw_any

    overall = "INCOMPLETE" if issue_mismatch or problems or not saw_any else ("FAIL" if findings else "PASS")
    (run_dir / "mirror_leakage_summary.md").write_text(
        "\n".join([
            f"# Mirror Leakage — {overall}", "",
            f"- issue: {args.issue}",
            f"- embedded_issue: {embedded_issue_id or '<none>'}",
            f"- issue_mismatch: {'yes' if issue_mismatch else 'no'}",
            f"- run_id: {run_id}",
            f"- path: {input_display}",
            f"- findings: {len(findings)}",
            f"- problems: {len(problems)}", "",
            "## Notes",
            "Mirror must simulate the learner (no teaching/imperatives).",
        ]) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": "mirror_leakage_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "embedded_issue_id": embedded_issue_id,
        "issue_mismatch": issue_mismatch,
        "seed": args.seed,
        "path": input_display,
        "findings": findings,
        "problems": problems,
    }
    write_json((run_dir / "mirror_leakage_report.json"), report)
    write_json(
        run_dir / "run.json",
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "deterministic": True,
            "outputs": ["mirror_leakage_report.json", "mirror_leakage_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    if issue_mismatch:
        print(f"INCOMPLETE: embedded issue_id {embedded_issue_id} does not match CLI issue {args.issue} (wrote {output_display})")
        return 2
    if problems:
        first = problems[0]
        detail = f"{first.get('field', 'input')}: {first.get('detail', 'malformed input')}"
        print(f"INCOMPLETE: malformed session input ({detail}) (wrote {output_display})")
        return 2
    if not saw_any:
        print(f"INCOMPLETE: no mirror answers present (wrote {output_display})")
        return 2
    if findings:
        print(f"FAIL: mirror role leakage in {len(findings)} turns (wrote {output_display})")
        return 1
    print(f"PASS: wrote outputs to {output_display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
