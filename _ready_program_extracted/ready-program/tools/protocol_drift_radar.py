#!/usr/bin/env python3
from __future__ import annotations

"""Protocol drift radar.

Scans run artifacts (turn_report.json / session_report.json) for signals that
the system violated role boundaries or began to "blend" roles.

This is a heuristic checker; it is deterministic and intended to catch
obvious regressions (e.g., mirror output sounding like the tutor).

Outputs:
  runs/<run_id>/protocol_drift_report.json
  runs/<run_id>/protocol_drift_summary.md
  runs/<run_id>/run.json

Exit codes: 0 PASS (no HIGH findings), 1 FAIL (HIGH findings), 2 INCOMPLETE
"""

import argparse
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

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_id() -> str:
    return make_run_id()


def _load_json(p: Path) -> dict:
    try:
        out = json.loads(
            p.read_text(encoding="utf-8", errors="replace"),
            object_pairs_hook=_no_duplicate_pairs,
        )
    except Exception:
        return {}
    return out if isinstance(out, dict) else {}


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


MAX_ITEMS_SCANNED = 5000
MAX_TEXT_SCAN_CHARS = 4000
SCAN_WINDOW_OVERLAP_CHARS = 256
MAX_INPUT_JSON_BYTES = 8_000_000
MAX_FINDINGS = 1000
SEVERITY_ORDER = ("HIGH", "WARN")
_CLIP_MARKER = "\n...[clipped middle]...\n"
_MARKUP_RE = re.compile(r"<[^>]+>|[`*_~]+")
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


def _clip_text(value: object) -> str:
    t = str(value or "")
    if len(t) <= MAX_TEXT_SCAN_CHARS:
        return t

    if MAX_TEXT_SCAN_CHARS <= len(_CLIP_MARKER):
        return t[:MAX_TEXT_SCAN_CHARS]

    head_chars = (MAX_TEXT_SCAN_CHARS - len(_CLIP_MARKER)) // 2
    tail_chars = MAX_TEXT_SCAN_CHARS - len(_CLIP_MARKER) - head_chars
    return t[:head_chars] + _CLIP_MARKER + t[-tail_chars:]


def _scan_windows(value: object) -> list[str]:
    text = str(value or "")
    if not text:
        return []
    if len(text) <= MAX_TEXT_SCAN_CHARS:
        return [text]

    overlap = max(0, min(SCAN_WINDOW_OVERLAP_CHARS, MAX_TEXT_SCAN_CHARS - 1))
    step = max(1, MAX_TEXT_SCAN_CHARS - overlap)

    windows: list[str] = []
    seen: set[tuple[int, int]] = set()
    starts = list(range(0, len(text), step))
    tail_start = max(0, len(text) - MAX_TEXT_SCAN_CHARS)
    starts.append(tail_start)

    for start in starts:
        end = min(len(text), start + MAX_TEXT_SCAN_CHARS)
        start = max(0, end - MAX_TEXT_SCAN_CHARS)
        bounds = (start, end)
        if bounds in seen:
            continue
        seen.add(bounds)
        windows.append(text[start:end])
        if end >= len(text):
            continue
    return windows


def _normalize_scan_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = unicodedata.normalize("NFKC", text).translate(_CONFUSABLES)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = _MARKUP_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _is_within(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _detect_artifact_kind(doc: object) -> str | None:
    if not isinstance(doc, dict):
        return None

    schema = str(doc.get("schema_version") or "").strip()
    payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
    root_turn_result = doc.get("turn_result") if isinstance(doc.get("turn_result"), dict) else None
    payload_turn_result = payload.get("turn_result") if isinstance(payload.get("turn_result"), dict) else None
    payload_session_report = payload.get("session_report") if isinstance(payload.get("session_report"), dict) else None
    has_root_session_turns = isinstance(doc.get("turns"), list)

    if schema == "witness_event@1":
        if payload_turn_result is not None:
            return "turn_report"
        if payload_session_report is not None:
            return "session_report"
        return None

    if schema == "turn_report@1":
        if payload_turn_result is not None or root_turn_result is not None:
            return "turn_report"
        return None

    if schema == "session_report@1":
        if has_root_session_turns:
            return "session_report"
        if payload_session_report is not None:
            return "session_report"
        return None

    if payload_turn_result is not None or root_turn_result is not None:
        return "turn_report"
    if payload_session_report is not None or has_root_session_turns:
        return "session_report"
    return None



def _add_item(items: list[dict], *, role: str, turn_index: int, text: object):
    clipped = _clip_text(text)
    if clipped:
        items.append(
            {
                "role": role,
                "turn_index": turn_index,
                "text": clipped,
                "scan_texts": _scan_windows(text),
            }
        )



def _iter_text_values(value: object, *, depth: int = 0, max_depth: int = 4):
    if depth > max_depth:
        return
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_text_values(nested, depth=depth + 1, max_depth=max_depth)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _iter_text_values(nested, depth=depth + 1, max_depth=max_depth)



def _iter_grounding_snippet_texts(prompt_meta: dict) -> list[str]:
    grounding = prompt_meta.get("grounding") if isinstance(prompt_meta, dict) else {}
    if not isinstance(grounding, dict):
        return []
    snippets = grounding.get("snippets") if isinstance(grounding.get("snippets"), list) else []
    out: list[str] = []
    for snippet in snippets:
        if isinstance(snippet, dict):
            text = snippet.get("text")
            if isinstance(text, str) and text.strip():
                out.append(text)
    return out



def _iter_session_turn_items(session_doc: object) -> list[dict]:
    items: list[dict] = []
    doc = session_doc if isinstance(session_doc, dict) else {}
    if doc.get("schema_version") == "witness_event@1":
        payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
        doc = payload.get("session_report") if isinstance(payload.get("session_report"), dict) else {}
    elif isinstance(doc.get("payload"), dict) and isinstance(doc.get("payload").get("session_report"), dict):
        doc = doc.get("payload").get("session_report")

    turns = doc.get("turns") if isinstance(doc.get("turns"), list) else []
    for t in turns:
        if len(items) >= MAX_ITEMS_SCANNED:
            break
        if not isinstance(t, dict):
            continue
        ti = _safe_int(t.get("turn_index"), 0)
        teach = t.get("teach") if isinstance(t.get("teach"), dict) else {}
        ev = t.get("eval") if isinstance(t.get("eval"), dict) else {}
        teach_prompt_meta = teach.get("prompt_meta") if isinstance(teach.get("prompt_meta"), dict) else {}
        eval_prompt_meta = ev.get("prompt_meta") if isinstance(ev.get("prompt_meta"), dict) else {}
        if t.get("node_title"):
            _add_item(items, role="session_node_title", turn_index=ti, text=t.get("node_title"))
        if teach.get("teaching_block"):
            _add_item(items, role="tutor_teach", turn_index=ti, text=teach.get("teaching_block"))
        if teach.get("question"):
            _add_item(items, role="tutor_question", turn_index=ti, text=teach.get("question"))
        if ev.get("evaluation"):
            _add_item(items, role="tutor_eval", turn_index=ti, text=ev.get("evaluation"))
        if ev.get("gaps"):
            _add_item(items, role="eval_gaps", turn_index=ti, text=ev.get("gaps"))
        if ev.get("next_action"):
            _add_item(items, role="eval_next_action", turn_index=ti, text=ev.get("next_action"))
        if ev.get("next_question"):
            _add_item(items, role="eval_next_question", turn_index=ti, text=ev.get("next_question"))
        for user_state_text in _iter_text_values(t.get("user_state")):
            _add_item(items, role="user_state", turn_index=ti, text=user_state_text)
        for snippet_text in _iter_grounding_snippet_texts(teach_prompt_meta):
            _add_item(items, role="teach_grounding_snippet", turn_index=ti, text=snippet_text)
        for snippet_text in _iter_grounding_snippet_texts(eval_prompt_meta):
            _add_item(items, role="eval_grounding_snippet", turn_index=ti, text=snippet_text)
        mirror = t.get("mirror") if isinstance(t.get("mirror"), dict) else {}
        if mirror.get("answer"):
            _add_item(items, role="mirror", turn_index=ti, text=mirror.get("answer"))
        if ev.get("mirror_answer"):
            _add_item(items, role="mirror_eval", turn_index=ti, text=ev.get("mirror_answer"))
        if teach_prompt_meta.get("backend_error"):
            _add_item(items, role="teach_backend_error", turn_index=ti, text=teach_prompt_meta.get("backend_error"))
        if eval_prompt_meta.get("backend_error"):
            _add_item(items, role="eval_backend_error", turn_index=ti, text=eval_prompt_meta.get("backend_error"))
    return items



def _iter_turn_items(turn_doc: object) -> list[dict]:
    items: list[dict] = []
    doc = turn_doc if isinstance(turn_doc, dict) else {}
    if doc.get("schema_version") == "witness_event@1":
        payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
        tr = payload.get("turn_result") if isinstance(payload.get("turn_result"), dict) else {}
    else:
        payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else {}
        tr = payload.get("turn_result") if isinstance(payload.get("turn_result"), dict) else {}
        if not tr:
            tr = doc.get("turn_result") if isinstance(doc.get("turn_result"), dict) else {}

    if not tr:
        return items

    ti = _safe_int(tr.get("turn_index"), 0)
    _add_item(items, role="tutor_reply", turn_index=ti, text=tr.get("reply"))
    if tr.get("teaching_block"):
        _add_item(items, role="turn_teaching_block", turn_index=ti, text=tr.get("teaching_block"))
    if tr.get("evaluation"):
        _add_item(items, role="turn_evaluation", turn_index=ti, text=tr.get("evaluation"))
    if tr.get("next_question"):
        _add_item(items, role="turn_next_question", turn_index=ti, text=tr.get("next_question"))
    mp = tr.get("mirror_prediction")
    if mp is not None:
        _add_item(items, role="mirror", turn_index=ti, text=mp)
    if tr.get("backend_error"):
        _add_item(items, role="turn_backend_error", turn_index=ti, text=tr.get("backend_error"))
    if tr.get("gaps"):
        _add_item(items, role="turn_gaps", turn_index=ti, text=tr.get("gaps"))
    if tr.get("next_action"):
        _add_item(items, role="turn_next_action", turn_index=ti, text=tr.get("next_action"))
    prompt_meta = tr.get("prompt_meta") if isinstance(tr.get("prompt_meta"), dict) else {}
    if prompt_meta.get("backend_error"):
        _add_item(items, role="turn_prompt_backend_error", turn_index=ti, text=prompt_meta.get("backend_error"))
    return items



def _iter_summary_markdown_items(summary_path: Path) -> list[dict]:
    items: list[dict] = []
    try:
        if int(summary_path.stat().st_size) > MAX_INPUT_JSON_BYTES:
            return items
    except OSError:
        return items

    try:
        text = summary_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return items

    if text.strip():
        _add_item(items, role="session_summary", turn_index=0, text=text)
    return items



def _collect_texts(target: Path) -> list[dict]:
    """Return a list of {role, turn_index, text} entries."""
    items: list[dict] = []

    if target.is_file():
        if target.name == "session_summary.md":
            return _iter_summary_markdown_items(target)
        try:
            if int(target.stat().st_size) > MAX_INPUT_JSON_BYTES:
                return items
        except OSError:
            return items
        doc = _load_json(target)
        kind = _detect_artifact_kind(doc)
        if kind == "turn_report":
            return _iter_turn_items(doc)
        if kind == "session_report":
            return _iter_session_turn_items(doc)
        return items

    if target.is_dir():
        for fn in ("turn_report.json", "session_report.json", "session_summary.md"):
            fp = target / fn
            if fp.exists():
                items.extend(_collect_texts(fp))
        return items

    return items


_ROLE_CONFUSION = [
    (re.compile(r"\bas your tutor\b", re.I), "mirror sounds like tutor"),
    (re.compile(r"\b(?:in\s+)?today'?s lesson\b", re.I), "lesson framing"),
    (re.compile(r"\blet'?s (?:learn|practice|start)\b", re.I), "tutor-style invitation"),
    (re.compile(r"\bbe sure to\b", re.I), "directive language"),
    (re.compile(r"\bthe key is to\b", re.I), "coaching language"),
    (re.compile(r"\ba good place to start is to\b", re.I), "coaching language"),
    (re.compile(r"\bone place to start is to\b", re.I), "coaching language"),
    (re.compile(r"\ba helpful place to begin is to\b", re.I), "coaching language"),
    (re.compile(r"\bit would be a good idea to\b", re.I), "coaching language"),
    (re.compile(r"\byou(?:'d| would)? be wise to\b", re.I), "coaching language"),
    (re.compile(r"\bmy first move would be\b", re.I), "coaching language"),
    (re.compile(r"\bit makes sense to\b", re.I), "coaching language"),
    (re.compile(r"\bwhy not\b", re.I), "coaching language"),
    (re.compile(r"^\s*(?:q\s*:\s*)?can you\b", re.I), "coaching question"),
    (re.compile(r"^\s*(?:q\s*:\s*)?would you\b", re.I), "coaching question"),
    (re.compile(r"^\s*(?:q\s*:\s*)?have you tried\b", re.I), "coaching question"),
    (re.compile(r"\bdeber[ií]as\b", re.I), "spanish directive"),
    (re.compile(r"\baseg[uú]rate de\b", re.I), "spanish directive"),
    (re.compile(r"(?:まずは|今日のレッスン|してみましょう|してください)", re.I), "japanese directive"),
]

_TUTOR_SELF_MISLABEL = [
    (re.compile(r"\bi am simulating the learner\b", re.I), "tutor claims learner simulation"),
    (re.compile(r"\bas the mirror\b", re.I), "tutor claims mirror role"),
    (re.compile(r"\bi am the mirror\b(?!\s*image\b)", re.I), "tutor claims mirror role"),
    (re.compile(r"\bmirror simulation\b", re.I), "tutor claims mirror role"),
]



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



def _scan_diagnostic_role_text(*, role: str, turn_index: object, text: str, low_text: str):
    if not any(token in low_text for token in ("mirror", "tutor", "learner", "lesson", "practice")):
        return

    for rx, msg in _ROLE_CONFUSION:
        if rx.search(text):
            yield {
                "severity": "HIGH",
                "turn_index": turn_index,
                "role": role,
                "message": f"diagnostic field contains {msg}",
            }
            return

    for rx, msg in _TUTOR_SELF_MISLABEL:
        if rx.search(text):
            yield {
                "severity": "HIGH",
                "turn_index": turn_index,
                "role": role,
                "message": f"diagnostic field contains {msg}",
            }
            return



def _iter_findings_for_text(*, role: str, turn_index: object, text: str):
    normalized = _normalize_scan_text(text)
    if not normalized:
        return
    low_text = normalized.lower()

    if role.startswith("mirror"):
        for rx, msg in _ROLE_CONFUSION:
            if rx.search(normalized):
                yield {"severity": "HIGH", "turn_index": turn_index, "role": role, "message": msg}
                return
        if _looks_like_imperative_coaching(normalized):
            yield {
                "severity": "HIGH",
                "turn_index": turn_index,
                "role": role,
                "message": "short imperative coaching sequence",
            }
        elif len(normalized) > 220 and "?" not in normalized and "not sure" not in low_text and "i think" not in low_text:
            yield {"severity": "WARN", "turn_index": turn_index, "role": role, "message": "mirror reply unusually assertive"}
        return

    if "backend_error" in role:
        for rx, msg in _ROLE_CONFUSION:
            if rx.search(normalized):
                yield {"severity": "HIGH", "turn_index": turn_index, "role": role, "message": f"backend error contains {msg}"}
                return
        for rx, msg in _TUTOR_SELF_MISLABEL:
            if rx.search(normalized):
                yield {"severity": "HIGH", "turn_index": turn_index, "role": role, "message": f"backend error contains {msg}"}
                return
        return

    if (
        role.endswith("_gaps")
        or role.endswith("_next_action")
        or role == "session_summary"
        or role == "user_state"
        or role.endswith("_grounding_snippet")
    ):
        yielded = False
        for finding in _scan_diagnostic_role_text(
            role=role,
            turn_index=turn_index,
            text=normalized,
            low_text=low_text,
        ):
            yielded = True
            yield finding
        if yielded:
            return
        if role == "session_summary":
            for rx, msg in _TUTOR_SELF_MISLABEL:
                if rx.search(normalized):
                    yield {
                        "severity": "HIGH",
                        "turn_index": turn_index,
                        "role": role,
                        "message": f"session summary contains {msg}",
                    }
                    return

    if "mirror" in low_text or "simulating the learner" in low_text:
        for rx, msg in _TUTOR_SELF_MISLABEL:
            if rx.search(normalized):
                yield {"severity": "HIGH", "turn_index": turn_index, "role": role, "message": msg}
                return


def _iter_raw_findings(items: list[dict]):
    for it in items:
        role = str(it.get("role") or "")
        turn_index = it.get("turn_index")
        scan_texts = it.get("scan_texts")
        if not isinstance(scan_texts, list) or not scan_texts:
            scan_texts = [it.get("text") or ""]

        seen: set[tuple[object, object, object, object]] = set()
        for raw_text in scan_texts:
            raw_text = str(raw_text or "").strip()
            if not raw_text:
                continue
            for finding in _iter_findings_for_text(role=role, turn_index=turn_index, text=raw_text):
                key = (finding.get("severity"), finding.get("turn_index"), finding.get("role"), finding.get("message"))
                if key in seen:
                    continue
                seen.add(key)
                yield finding



def _severity_sort_key(severity: object) -> tuple[int, str]:
    sev = str(severity or "").upper()
    try:
        return (SEVERITY_ORDER.index(sev), sev)
    except ValueError:
        return (len(SEVERITY_ORDER), sev)



def _findings(items: list[dict]) -> tuple[list[dict], dict, dict]:
    raw_findings = list(_iter_raw_findings(items))
    total_by_severity: dict[str, int] = {}
    findings_by_severity: dict[str, list[dict]] = {}
    for finding in raw_findings:
        sev = str(finding.get("severity") or "WARN").upper()
        total_by_severity[sev] = total_by_severity.get(sev, 0) + 1
        findings_by_severity.setdefault(sev, []).append(finding)

    ordered_findings: list[dict] = []
    for sev in sorted(findings_by_severity.keys(), key=_severity_sort_key):
        ordered_findings.extend(findings_by_severity[sev])

    kept_findings = ordered_findings[:MAX_FINDINGS]
    kept_by_severity: dict[str, int] = {}
    for finding in kept_findings:
        sev = str(finding.get("severity") or "WARN").upper()
        kept_by_severity[sev] = kept_by_severity.get(sev, 0) + 1
    return kept_findings, total_by_severity, kept_by_severity



def main() -> int:
    p = argparse.ArgumentParser(prog="protocol_drift_radar")
    p.add_argument("path", help="runs/<run_id>/ or a JSON report")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument(
        "--allow-external-path",
        action="store_true",
        help="Allow scanning a path outside repository root.",
    )
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    target = Path(args.path).resolve()
    if not target.exists():
        print(f"INCOMPLETE: not found: {target}")
        return 2
    if not args.allow_external_path and not _is_within(_REPO_ROOT, target):
        print("INCOMPLETE: path must be within repo root unless --allow-external-path is set")
        return 2

    items = _collect_texts(target)
    if not items:
        print("INCOMPLETE: no recognizable artifacts found")
        return 2

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)

    findings, findings_total_by_severity, findings_kept_by_severity = _findings(items)
    total_findings = sum(findings_total_by_severity.values())
    kept_findings = len(findings)
    truncated_findings = max(0, total_findings - kept_findings)
    high_total = findings_total_by_severity.get("HIGH", 0)

    report = {
        "schema_version": "protocol_drift_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "target": str(target),
        "items_scanned": len(items),
        "findings_total": total_findings,
        "findings_truncated": truncated_findings,
        "findings_total_by_severity": findings_total_by_severity,
        "findings_kept_by_severity": findings_kept_by_severity,
        "findings": findings,
    }
    write_json((run_dir / "protocol_drift_report.json"), report)

    lines = [
        "# Protocol Drift Radar Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- target: `{target}`",
        f"- findings: total=`{total_findings}` kept=`{kept_findings}` truncated=`{truncated_findings}` (HIGH={high_total})",
        "",
    ]
    for f in findings[:50]:
        lines.append(f"- {f['severity']} t{f.get('turn_index')} {f.get('role')}: {f.get('message')}")
    (run_dir / "protocol_drift_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["protocol_drift_report.json", "protocol_drift_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    ok = high_total == 0
    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
