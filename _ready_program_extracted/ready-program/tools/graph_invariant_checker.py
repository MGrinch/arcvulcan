#!/usr/bin/env python3
from __future__ import annotations

"""Knowledge-graph invariant checker.

Validates `knowledge_graph.json` invariants and (optionally) cross-checks against
`session_report.json` when present.

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE
"""

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id
from xyzgl.knowledge.graph import (
    MAX_FLAGS_PER_NODE,
    MAX_GRAPH_BYTES,
    MAX_GRAPH_NODES,
    MAX_KEYWORDS_PER_NODE,
    MAX_SUMMARY_CHARS,
    MAX_TITLE_CHARS,
    MAX_TOKEN_CHARS,
)


_ABS_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9_.-])(?:[A-Z]:\\|/)[^\s]+")
_ALLOWED_ROOT_KEYS = {"schema_version", "nodes"}
_ALLOWED_NODE_KEYS = {
    "node_id",
    "title",
    "summary",
    "required_keywords",
    "confidence",
    "fragility_flags",
    "last_verified_turn",
}
_REQUIRED_NODE_KEYS = tuple(sorted(_ALLOWED_NODE_KEYS))


def _run_id() -> str:
    return make_run_id()


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_json(p: Path) -> object:
    last_err: Exception | None = None
    for _ in range(3):
        try:
            raw = p.read_bytes()
            try:
                txt = raw.decode("utf-8")
            except UnicodeDecodeError:
                txt = raw.decode("utf-8", errors="replace")
            return json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
        except json.JSONDecodeError as e:
            last_err = e
            time.sleep(0.05)
    raise ValueError(f"invalid JSON: {p} ({last_err})")


def _to_int(v: object, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _extract_session_turns(session_doc: dict) -> list[dict] | None:
    if not isinstance(session_doc, dict):
        return None
    doc = session_doc
    if doc.get("schema_version") == "witness_event@1":
        doc = (doc.get("payload") or {}).get("session_report") or {}
    if isinstance(doc, dict) and doc.get("schema_version") == "session_report@1":
        turns = doc.get("turns")
        return turns if isinstance(turns, list) else None

    # Legacy fallback: witness payload.session_report without explicit schema tag.
    payload = session_doc.get("payload") or {}
    sr = payload.get("session_report")
    if isinstance(sr, dict):
        turns = sr.get("turns")
        return turns if isinstance(turns, list) else None
    return None


def _collect_embedded_issue_ids(session_doc: object) -> list[str]:
    if not isinstance(session_doc, dict):
        return []

    seen: set[str] = set()
    out: list[str] = []

    def _add(value: object) -> None:
        issue = str(value or "").strip()
        if issue and issue not in seen:
            seen.add(issue)
            out.append(issue)

    _add(session_doc.get("issue_id"))
    payload = session_doc.get("payload")
    if isinstance(payload, dict):
        _add(payload.get("issue_id"))
        sr = payload.get("session_report")
        if isinstance(sr, dict):
            _add(sr.get("issue_id"))

    return out


def _extract_embedded_issue_id(session_doc: object) -> str | None:
    issue_ids = _collect_embedded_issue_ids(session_doc)
    if not issue_ids:
        return None
    return issue_ids[-1]


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


def _sanitize_text(text: object, replacements: dict[str, str] | None = None) -> str:
    out = str(text or "")
    for src, dest in (replacements or {}).items():
        if not src:
            continue
        variants = {src, src.replace("\\", "/")}
        try:
            resolved = str(Path(src).resolve())
            variants.add(resolved)
            variants.add(resolved.replace("\\", "/"))
        except Exception:
            pass
        for variant in sorted(variants, key=len, reverse=True):
            out = out.replace(variant, dest)
    return _ABS_PATH_RE.sub("<path>", out)


def _is_number_without_bool(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _problem_node_label(index: int, node_id: str | None) -> str:
    cleaned = (node_id or "").strip()
    return cleaned or f"node[{index}]"


def _validate_token_list(
    value: object,
    *,
    field_name: str,
    node_label: str,
    max_items: int,
    problems: list[str],
) -> None:
    if not isinstance(value, list):
        problems.append(f"node {node_label}: {field_name} not list")
        return
    if len(value) > max_items:
        problems.append(f"node {node_label}: {field_name} exceeds max_items {max_items}")
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            problems.append(f"node {node_label}: {field_name}[{idx}] not string")
            continue
        trimmed = item.strip()
        if not trimmed:
            problems.append(f"node {node_label}: {field_name}[{idx}] empty")
            continue
        if trimmed != item:
            problems.append(f"node {node_label}: {field_name}[{idx}] has surrounding whitespace")
        if len(trimmed) > MAX_TOKEN_CHARS:
            problems.append(
                f"node {node_label}: {field_name}[{idx}] exceeds {MAX_TOKEN_CHARS} chars"
            )


def _write_bundle(
    out_dir: Path,
    *,
    run_id: str,
    issue: str,
    embedded_issue_id: str | None,
    issue_mismatch: bool,
    overall: str,
    source: str,
    node_count: int,
    problems: list[str],
) -> None:
    write_json(
        (out_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": issue,
            "seed": None,
            "deterministic": True,
            "outputs": ["graph_invariant_report.json", "graph_invariant_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )
    (out_dir / "graph_invariant_summary.md").write_text(
        "\n".join(
            [
                f"# Graph Invariant Summary — {overall}",
                "",
                f"- issue: {issue}",
                f"- embedded_issue: {embedded_issue_id or '<none>'}",
                f"- issue_mismatch: {'yes' if issue_mismatch else 'no'}",
                f"- run_id: {run_id}",
                f"- source: {source}",
                f"- node_count: {node_count}",
                f"- problems: {len(problems)}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(prog="graph_invariant_checker")
    ap.add_argument("path", help="runs/<run_id>/ dir")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--strict", action="store_true", help="Stricter checks")
    args = ap.parse_args()

    target = Path(args.path)
    source_display = _display_path(target)
    if not target.exists() or not target.is_dir():
        print(_sanitize_text(f"FAIL: not a dir: {target}", {str(target): source_display}))
        return 1

    run_id = _run_id()
    out_dir = allocate_run_dir(run_id)
    output_display = _display_path(out_dir)
    kg_path = target / "knowledge_graph.json"
    replacements = {
        str(target): source_display,
        str(kg_path): f"{source_display}/knowledge_graph.json" if source_display != "<path>" else "knowledge_graph.json",
    }
    problems: list[str] = []
    details: str | None = None
    embedded_issue_id: str | None = None
    issue_mismatch = False
    nodes: list[dict] = []
    max_turn_seen = -1
    exit_code = 0
    parse_incomplete = False

    if not kg_path.exists():
        overall = "INCOMPLETE"
        exit_code = 2
        details = "knowledge_graph.json not found"
    else:
        try:
            kg_size = int(kg_path.stat().st_size)
            if kg_size > MAX_GRAPH_BYTES:
                problems.append(
                    f"knowledge_graph.json exceeds maximum size: {kg_size} > {MAX_GRAPH_BYTES}"
                )
        except Exception as e:
            overall = "INCOMPLETE"
            exit_code = 2
            details = _sanitize_text(f"could not stat graph file: {e}", replacements)
            parse_incomplete = True

        kg: object = {}
        if not parse_incomplete:
            try:
                kg = _load_json(kg_path)
            except Exception as e:
                overall = "INCOMPLETE"
                exit_code = 2
                details = _sanitize_text(e, replacements)
                parse_incomplete = True

        if not parse_incomplete:
            if not isinstance(kg, dict):
                problems.append("knowledge_graph root must be an object")
                kg = {}
            else:
                extra_root_keys = sorted(str(k) for k in kg.keys() if k not in _ALLOWED_ROOT_KEYS)
                if extra_root_keys:
                    problems.append(f"unexpected root keys: {', '.join(extra_root_keys)}")
                if kg.get("schema_version") != "knowledge_graph@1":
                    problems.append("schema_version must be knowledge_graph@1")

                raw_nodes = kg.get("nodes")
                if not isinstance(raw_nodes, list):
                    problems.append("nodes must be a list")
                    raw_nodes = []
                else:
                    if len(raw_nodes) > MAX_GRAPH_NODES:
                        problems.append(f"nodes exceeds max_items {MAX_GRAPH_NODES}")

                seen: set[str] = set()
                truncated_ids: dict[str, str] = {}
                last_id = ""
                for i, raw_node in enumerate(raw_nodes):
                    if not isinstance(raw_node, dict):
                        problems.append(f"node[{i}] must be object")
                        continue
                    nodes.append(raw_node)

                    extra_node_keys = sorted(str(k) for k in raw_node.keys() if k not in _ALLOWED_NODE_KEYS)
                    if extra_node_keys:
                        problems.append(
                            f"node[{i}] unexpected keys: {', '.join(extra_node_keys)}"
                        )

                    missing = [key for key in _REQUIRED_NODE_KEYS if key not in raw_node]
                    if missing:
                        problems.append(f"node[{i}] missing required fields: {', '.join(sorted(missing))}")

                    node_id_raw = raw_node.get("node_id")
                    node_label = _problem_node_label(i, node_id_raw if isinstance(node_id_raw, str) else None)
                    nid = ""
                    if not isinstance(node_id_raw, str):
                        problems.append(f"node[{i}]: node_id not string")
                    else:
                        nid = node_id_raw.strip()
                        node_label = _problem_node_label(i, nid)
                        if not nid:
                            problems.append(f"node[{i}]: node_id empty")
                        if nid != node_id_raw:
                            problems.append(f"node {node_label}: node_id has surrounding whitespace")
                        if len(nid) > MAX_TOKEN_CHARS:
                            problems.append(
                                f"node {node_label}: node_id exceeds {MAX_TOKEN_CHARS} chars"
                            )
                        truncated = nid[:MAX_TOKEN_CHARS]
                        prev = truncated_ids.get(truncated)
                        if prev is not None and prev != nid:
                            problems.append(
                                f"node_id collision after {MAX_TOKEN_CHARS}-char truncation: {prev!r} vs {nid!r}"
                            )
                        elif truncated:
                            truncated_ids[truncated] = nid
                        if nid in seen:
                            problems.append(f"duplicate node_id: {nid}")
                        if args.strict and last_id and nid and nid < last_id:
                            problems.append("nodes not sorted by node_id")
                        if nid:
                            seen.add(nid)
                            last_id = nid

                    title = raw_node.get("title")
                    if not isinstance(title, str):
                        problems.append(f"node {node_label}: title not string")
                    else:
                        if not title.strip():
                            problems.append(f"node {node_label}: title empty")
                        if len(title.strip()) > MAX_TITLE_CHARS:
                            problems.append(
                                f"node {node_label}: title exceeds {MAX_TITLE_CHARS} chars"
                            )

                    summary = raw_node.get("summary")
                    if not isinstance(summary, str):
                        problems.append(f"node {node_label}: summary not string")
                    else:
                        if not summary.strip():
                            problems.append(f"node {node_label}: summary empty")
                        if len(summary.strip()) > MAX_SUMMARY_CHARS:
                            problems.append(
                                f"node {node_label}: summary exceeds {MAX_SUMMARY_CHARS} chars"
                            )

                    confidence = raw_node.get("confidence")
                    if not _is_number_without_bool(confidence):
                        problems.append(f"node {node_label}: confidence not a number")
                    else:
                        cf = float(confidence)
                        if (not math.isfinite(cf)) or cf < 0.0 or cf > 1.0:
                            problems.append(f"node {node_label}: confidence out of [0..1]")

                    last_verified_turn = raw_node.get("last_verified_turn")
                    if isinstance(last_verified_turn, bool) or not isinstance(last_verified_turn, int):
                        problems.append(f"node {node_label}: last_verified_turn not int")
                    else:
                        if last_verified_turn < -1:
                            problems.append(f"node {node_label}: last_verified_turn < -1")
                        max_turn_seen = max(max_turn_seen, last_verified_turn)

                    _validate_token_list(
                        raw_node.get("required_keywords"),
                        field_name="required_keywords",
                        node_label=node_label,
                        max_items=MAX_KEYWORDS_PER_NODE,
                        problems=problems,
                    )
                    _validate_token_list(
                        raw_node.get("fragility_flags"),
                        field_name="fragility_flags",
                        node_label=node_label,
                        max_items=MAX_FLAGS_PER_NODE,
                        problems=problems,
                    )

            session_path = target / "session_report.json"
            replacements[str(session_path)] = (
                f"{source_display}/session_report.json" if source_display != "<path>" else "session_report.json"
            )
            if session_path.exists():
                try:
                    sd = _load_json(session_path)
                except Exception as e:
                    overall = "INCOMPLETE"
                    exit_code = 2
                    details = _sanitize_text(f"session_report parse failed: {e}", replacements)
                    parse_incomplete = True
                    sd = None
                if not parse_incomplete:
                    embedded_issue_ids = _collect_embedded_issue_ids(sd)
                    embedded_issue_id = embedded_issue_ids[-1] if embedded_issue_ids else None
                    unique_issue_ids = sorted(set(embedded_issue_ids))
                    if len(unique_issue_ids) > 1:
                        issue_mismatch = True
                        problems.append(
                            "conflicting embedded issue_ids: " + ", ".join(unique_issue_ids)
                        )
                    elif embedded_issue_id and embedded_issue_id != args.issue:
                        issue_mismatch = True
                        problems.append(
                            f"embedded issue_id {embedded_issue_id} does not match CLI issue {args.issue}"
                        )
                    turns = _extract_session_turns(sd) if isinstance(sd, dict) else None
                    if turns is None:
                        problems.append("session_report present but could not parse turns")
                    else:
                        max_turn_idx = max([_to_int((t or {}).get("turn_index", -1), -1) for t in turns] or [-1])
                        for n in nodes:
                            nid = str(n.get("node_id") or "").strip()
                            lvt = _to_int(n.get("last_verified_turn", -1), -1)
                            if lvt > max_turn_idx:
                                problems.append(
                                    f"node {nid or '<missing>'}: last_verified_turn {lvt} beyond session max {max_turn_idx}"
                                )

        if parse_incomplete or issue_mismatch:
            overall = "INCOMPLETE"
            exit_code = 2
            if issue_mismatch and not details:
                details = f"conflicting embedded issue_ids in {session_path.name}"
        else:
            overall = "PASS" if not problems else "FAIL"
            exit_code = 0 if overall == "PASS" else 1

    report = {
        "schema_version": "graph_invariant_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "embedded_issue_id": embedded_issue_id,
        "issue_mismatch": issue_mismatch,
        "source": source_display,
        "overall": overall,
        "node_count": len(nodes),
        "max_last_verified_turn": max_turn_seen,
        "problems": problems,
    }
    if details:
        report["details"] = details

    write_json((out_dir / "graph_invariant_report.json"), report)
    _write_bundle(
        out_dir,
        run_id=run_id,
        issue=args.issue,
        embedded_issue_id=embedded_issue_id,
        issue_mismatch=issue_mismatch,
        overall=overall,
        source=source_display,
        node_count=len(nodes),
        problems=problems,
    )

    if overall == "INCOMPLETE" and details:
        print(f"INCOMPLETE: {details}")
        print(f"INCOMPLETE: wrote outputs to {output_display}")
    else:
        print(f"{overall}: wrote outputs to {output_display}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
