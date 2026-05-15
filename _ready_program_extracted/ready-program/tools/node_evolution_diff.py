#!/usr/bin/env python3
from __future__ import annotations

"""Node evolution diff.

Diffs two knowledge_graph.json snapshots and explains changes.

Optional: if you pass --session-report, it will try to link node changes to
turns that closed nodes.

Exit codes: 0 PASS, 1 FAIL.
"""

import argparse
import html
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))


def _md_inline(value: object) -> str:
    if isinstance(value, str):
        raw = value
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    # Keep inline markdown stable for untrusted values.
    raw = raw.replace("`", "\\`").replace("\n", "\\n")
    return html.escape(raw)


def _index_nodes(g: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for n in (g.get("nodes") or []):
        nid = str(n.get("node_id") or "").strip()
        if nid:
            out[nid] = n
    return out


def _turn_next_action(turn: dict) -> str:
    eval_block = turn.get("eval")
    if isinstance(eval_block, dict):
        action = str(eval_block.get("next_action") or "").strip()
        if action:
            return action
    return str(turn.get("next_action") or "").strip()


def main() -> int:
    p = argparse.ArgumentParser(prog="node_evolution_diff")
    p.add_argument("before", help="path to knowledge_graph.json (before)")
    p.add_argument("after", help="path to knowledge_graph.json (after)")
    p.add_argument("--session-report", help="optional session_report.json for linking")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    b = Path(args.before)
    a = Path(args.after)
    if not b.exists() or not a.exists():
        print("FAIL: missing input graph file")
        return 1

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)

    gb = _load_json(b)
    ga = _load_json(a)
    nb = _index_nodes(gb)
    na = _index_nodes(ga)

    closed_turns: dict[str, int] = {}
    if args.session_report:
        srp = Path(args.session_report)
        if srp.exists():
            sr = _load_json(srp)
            for t in (sr.get("turns") or []):
                nid = str(t.get("node_id") or "").strip()
                if nid and _turn_next_action(t).upper() == "CLOSE_NODE":
                    closed_turns[nid] = int(t.get("turn_index") or -1)

    added = sorted(set(na) - set(nb))
    removed = sorted(set(nb) - set(na))
    common = sorted(set(na) & set(nb))

    changed: list[dict] = []
    for nid in common:
        bnode = nb[nid]
        anode = na[nid]
        fields = [
            "confidence",
            "last_verified_turn",
            "fragility_flags",
            "required_keywords",
            "summary",
            "title",
        ]
        diffs: dict[str, dict] = {}
        for f in fields:
            if bnode.get(f) != anode.get(f):
                diffs[f] = {"before": bnode.get(f), "after": anode.get(f)}
        if diffs:
            changed.append(
                {
                    "node_id": nid,
                    "diff": diffs,
                    "linked_close_turn": closed_turns.get(nid, None),
                }
            )

    report = {
        "schema_version": "node_evolution_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "before": str(b),
        "after": str(a),
        "added": added,
        "removed": removed,
        "changed": changed,
    }
    write_json((run_dir / "node_evolution_report.json"), report)

    md: list[str] = [
        "# Node Evolution Diff",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        "",
        f"## Added ({len(added)})",
    ]
    md.extend([f"- `{_md_inline(x)}`" for x in added] or ["- (none)"])
    md.append("")
    md.append(f"## Removed ({len(removed)})")
    md.extend([f"- `{_md_inline(x)}`" for x in removed] or ["- (none)"])
    md.append("")
    md.append(f"## Changed ({len(changed)})")
    if not changed:
        md.append("- (none)")
    for c in changed:
        nid = c["node_id"]
        link = c.get("linked_close_turn")
        md.append(f"- **{_md_inline(nid)}**" + (f" (closed at turn {link})" if link is not None else ""))
        for k, v in (c.get("diff") or {}).items():
            md.append(f"  - `{_md_inline(k)}`: `{_md_inline(v.get('before'))}` -> `{_md_inline(v.get('after'))}`")
    (run_dir / "node_evolution_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["node_evolution_report.json", "node_evolution_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(f"PASS: wrote outputs to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
