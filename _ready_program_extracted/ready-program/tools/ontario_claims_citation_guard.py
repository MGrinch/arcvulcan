#!/usr/bin/env python3
from __future__ import annotations
"""Ontario claims citation guard.

Scans Tutor outputs (turn_report.json or session_report.json) for Ontario- or
code-specific terms and checks whether the output is grounded.

Grounded means either:
  - the prompt meta shows injected grounding snippets, and/or
  - the output contains explicit citation markers like [src:ID:ordinal]

This is a heuristic gate meant to catch obvious "Ontario specifics without
support" regressions.

Exit codes:
  0 PASS (no FAIL findings, or audit-only mode)
  1 FAIL (enforced mode with FAIL findings)
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


_CITE_RE = re.compile(r"\[src:([A-Za-z0-9_.-]+):([0-9]{1,6})\]", re.IGNORECASE)
_EXCERPT_CHARS = 220

_KEYWORDS = [
    "ontario",
    "cwb",
    "w47",
    "w47.1",
    "w59",
    "w117",
    "csa",
    "o. reg",
    "reg.",
    "wsib",
    "conestoga",
    "tssa",
]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_json(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", errors="replace")
    data = json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
    return data if isinstance(data, dict) else {}


def _grounding_refs(meta: dict) -> set[tuple[str, int]]:
    refs: set[tuple[str, int]] = set()
    pm = _as_dict(_as_dict(meta).get("prompt_meta"))
    gd = _as_dict(pm.get("grounding"))
    snippets = _as_list(gd.get("snippets"))
    for sn in snippets:
        sd = _as_dict(sn)
        sid = str(sd.get("source_id") or "").strip().lower()
        ord_raw = sd.get("passage_ordinal")
        if not sid:
            continue
        try:
            ord_i = int(ord_raw)
        except Exception:
            continue
        if ord_i < 0:
            continue
        refs.add((sid, ord_i))
    return refs


def _keywords_in(text: str) -> list[str]:
    t = (text or "").lower()
    return [k for k in _KEYWORDS if k in t]


def _short_excerpt(text: str, *, max_chars: int = _EXCERPT_CHARS) -> str:
    if max_chars <= 0:
        return ""
    out: list[str] = []
    used = 0
    for ln in str(text or "").splitlines():
        part = ln.strip()
        if not part:
            continue
        add = len(part) + (1 if out else 0)
        if used + add > max_chars:
            remain = max_chars - used
            if remain > 0:
                if out:
                    out.append(" ")
                    remain -= 1
                out.append(part[:remain])
            return "".join(out) + ("..." if text else "")
        if out:
            out.append(" ")
            used += 1
        out.append(part)
        used += len(part)
        if used >= max_chars:
            return "".join(out)
    joined = "".join(out)
    if not joined:
        t = str(text or "")
        joined = t[:max_chars]
        if len(t) > max_chars:
            joined += "..."
    return joined


def _scan_text(
    location: str,
    text: str,
    *,
    grounding_refs: set[tuple[str, int]],
    include_excerpt: bool,
) -> list[dict]:
    kws = _keywords_in(text)
    if not kws:
        return []
    has_grounding = bool(grounding_refs)
    all_cites: list[tuple[str, int]] = []
    for m in _CITE_RE.finditer(text or ""):
        sid = str(m.group(1) or "").strip().lower()
        ord_i = int(m.group(2))
        all_cites.append((sid, ord_i))
    valid_cites = [c for c in all_cites if c in grounding_refs]
    has_cite = bool(all_cites)
    severity = "FAIL" if (not has_grounding and not has_cite) else "WARN"
    excerpt = _short_excerpt(text, max_chars=_EXCERPT_CHARS)
    finding = {
        "severity": severity,
        "location": location,
        "keywords": kws,
        "has_grounding": bool(has_grounding),
        "has_citations": bool(has_cite),
        "citation_count": len(all_cites),
        "valid_citation_count": len(valid_cites),
        "invalid_citation_count": max(0, len(all_cites) - len(valid_cites)),
        "excerpt_hash": hashlib.sha256(excerpt.encode("utf-8", errors="replace")).hexdigest()[:16],
        "excerpt_length": len(excerpt),
    }
    if include_excerpt:
        finding["excerpt"] = excerpt
    return [finding]


def _extract_turn_result(doc: dict) -> dict:
    payload = _as_dict(doc.get("payload"))
    payload_turn_result = _as_dict(payload.get("turn_result"))
    root_turn_result = _as_dict(doc.get("turn_result"))
    if str(doc.get("schema_version") or "") == "witness_event@1":
        return payload_turn_result
    return payload_turn_result or root_turn_result


def _extract_session_report(doc: dict) -> dict:
    payload = _as_dict(doc.get("payload"))
    payload_session_report = _as_dict(payload.get("session_report"))
    if str(doc.get("schema_version") or "") == "witness_event@1":
        return payload_session_report
    return payload_session_report or doc


def _scan_named_fields(
    *,
    prefix: str,
    fields: list[tuple[str, object]],
    grounding_refs: set[tuple[str, int]],
    include_excerpt: bool,
) -> list[dict]:
    findings: list[dict] = []
    for suffix, value in fields:
        text = value if isinstance(value, str) else ""
        findings.extend(
            _scan_text(
                f"{prefix}.{suffix}",
                text,
                grounding_refs=grounding_refs,
                include_excerpt=include_excerpt,
            )
        )
    return findings


def main() -> int:
    p = argparse.ArgumentParser(prog="ontario_claims_citation_guard")
    p.add_argument("path", help="turn_report.json, session_report.json, or runs/<run_id>/ dir")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument(
        "--enforce",
        action="store_true",
        help="Fail the run if any FAIL findings are present (default: audit-only)",
    )
    p.add_argument(
        "--include-excerpts",
        action="store_true",
        help="Include redacted excerpts in findings (default off for artifact safety)",
    )
    args = p.parse_args()

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    target = Path(args.path)
    if not target.exists():
        print(f"FAIL: not found: {target}")
        return 1

    # Resolve input file.
    candidates: list[Path] = []
    if target.is_dir():
        for fn in ("turn_report.json", "session_report.json"):
            fp = target / fn
            if fp.exists():
                candidates.append(fp)
    else:
        candidates = [target]

    if not candidates:
        print("FAIL: no report files found")
        return 1

    findings: list[dict] = []
    scanned_path = str(candidates[0])

    for fp in candidates:
        outer = _load_json(fp)
        doc = _extract_session_report(outer)
        turn_result = _extract_turn_result(outer)
        schema = str((doc or {}).get("schema_version") or outer.get("schema_version") or "")

        if fp.name == "turn_report.json" or schema.startswith("turn_report") or turn_result:
            tr = turn_result
            refs = _grounding_refs({"prompt_meta": tr.get("prompt_meta")})
            turn_findings = _scan_named_fields(
                prefix="turn",
                fields=[
                    ("reply", tr.get("reply")),
                    ("teaching_block", tr.get("teaching_block")),
                    ("evaluation", tr.get("evaluation")),
                    ("gaps", tr.get("gaps")),
                    ("next_action", tr.get("next_action")),
                    ("next_question", tr.get("next_question")),
                ],
                grounding_refs=refs,
                include_excerpt=bool(args.include_excerpts),
            )
            tid = _as_int(tr.get("turn_index"), 0)
            for f in turn_findings:
                f["turn_index"] = tid
            findings.extend(turn_findings)
            continue

        if fp.name == "session_report.json" or schema.startswith("session_report"):
            turns = _as_list(doc.get("turns"))
            for t in turns:
                td = _as_dict(t)
                teach = _as_dict(td.get("teach"))
                ev = _as_dict(td.get("eval"))
                refs_teach = _grounding_refs({"prompt_meta": teach.get("prompt_meta")})
                refs_eval = _grounding_refs({"prompt_meta": ev.get("prompt_meta")})
                tid = _as_int(td.get("turn_index"), 0)
                node_id = str(td.get("node_id") or "")

                f1 = _scan_named_fields(
                    prefix=f"turns[{tid}].teach",
                    fields=[
                        ("teaching_block", teach.get("teaching_block")),
                        ("question", teach.get("question")),
                    ],
                    grounding_refs=refs_teach,
                    include_excerpt=bool(args.include_excerpts),
                )
                f2 = _scan_named_fields(
                    prefix=f"turns[{tid}].eval",
                    fields=[
                        ("evaluation", ev.get("evaluation")),
                        ("gaps", ev.get("gaps")),
                        ("next_action", ev.get("next_action")),
                        ("next_question", ev.get("next_question")),
                    ],
                    grounding_refs=refs_eval,
                    include_excerpt=bool(args.include_excerpts),
                )
                for f in (f1 + f2):
                    f["turn_index"] = tid
                    f["node_id"] = node_id
                findings.extend(f1 + f2)

    report = {
        "schema_version": "ontario_claims_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "path": scanned_path,
        "enforced": bool(args.enforce),
        "include_excerpts": bool(args.include_excerpts),
        "findings": findings,
    }
    write_json((run_dir / "ontario_claims_report.json"), report)

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["ontario_claims_report.json", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL"},
    }
    write_json((run_dir / "run.json"), run_meta)

    fail_findings = [f for f in findings if f.get("severity") == "FAIL"]
    if args.enforce and fail_findings:
        print(f"FAIL: {len(fail_findings)} unsupported Ontario-claim findings (wrote {run_dir})")
        return 1
    print(f"PASS: wrote outputs to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
