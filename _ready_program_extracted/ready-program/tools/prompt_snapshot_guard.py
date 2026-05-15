#!/usr/bin/env python3
from __future__ import annotations

"""Prompt snapshot guard.

The #1 regression class in Daedalus is "silent prompt drift": small changes to
prompt markers, ordering, or the protocol/grounding blocks.

This tool:
  - builds a small set of canonical Tutor prompts
  - hashes them (sha256)
  - compares against snapshots/prompt_snapshots.json

Use --update to intentionally refresh the baseline.

Exit codes:
  0 PASS
  1 FAIL
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id
from issue_id import validate_issue_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import (
    GROUNDING_CLOSE,
    GROUNDING_OPEN,
    PROTOCOL_CLOSE,
    PROTOCOL_OPEN,
    build_tutor_prompt,
)

MAX_SNAPSHOT_BYTES = 2_000_000
SNAPSHOT_SCHEMA_VERSION = "prompt_snapshots@1"


def _run_id() -> str:
    return make_run_id()

def _sha256(s: str) -> str:
    h = hashlib.sha256()
    h.update((s or "").encode("utf-8"))
    return h.hexdigest()


def _cases(repo_root: Path) -> list[dict]:
    """Canonical cases.

    Keep these small and stable; they should NOT depend on network.
    """

    return [
        {
            "name": "no_protocol_no_grounding",
            "cfg": XYZGLConfig(protocol_reground_every=0, grounding_mode="off"),
            "turn_index": 1,
            "user_text": "fit-up is uneven, should I keep tacking?",
            "expected_meta": {"protocol_regrounded": False, "grounding_enabled": False},
            "expected_prompt_blocks": {"protocol": False, "grounding": False},
        },
        {
            "name": "protocol_only",
            "cfg": XYZGLConfig(protocol_reground_every=1, grounding_mode="off"),
            "turn_index": 0,
            "user_text": "Explain 2F vs 1F.",
            "expected_meta": {"protocol_regrounded": True, "grounding_enabled": False},
        },
        {
            "name": "grounding_only",
            "cfg": XYZGLConfig(protocol_reground_every=0, grounding_mode="local", grounding_dir="curriculum"),
            "turn_index": 1,
            "user_text": "SMAW arc length too long symptoms",
            "expected_meta": {"protocol_regrounded": False, "grounding_enabled": True},
        },
        {
            "name": "protocol_and_grounding",
            "cfg": XYZGLConfig(protocol_reground_every=1, grounding_mode="local", grounding_dir="curriculum"),
            "turn_index": 0,
            "user_text": "What causes lack of fusion in a fillet?",
            "expected_meta": {"protocol_regrounded": True, "grounding_enabled": True},
        },
        {
            "name": "protocol_periodic_off_turn",
            "cfg": XYZGLConfig(protocol_reground_every=3, grounding_mode="off"),
            "turn_index": 1,
            "user_text": "basic travel angle advice",
            "expected_meta": {"protocol_regrounded": False, "grounding_enabled": False},
        },
    ]


def _snapshot_path(repo_root: Path, *, create_parent: bool = False) -> Path:
    repo_root_resolved = repo_root.resolve()
    snap_dir = repo_root / "snapshots"
    if snap_dir.exists() and snap_dir.is_symlink():
        raise RuntimeError("snapshots directory is a symlink; refusing write")
    if create_parent:
        snap_dir.mkdir(parents=True, exist_ok=True)
    snap_dir_resolved = snap_dir.resolve(strict=False)
    try:
        snap_dir_resolved.relative_to(repo_root_resolved)
    except Exception as e:
        raise RuntimeError("snapshots directory escapes repo root") from e
    return snap_dir_resolved / "prompt_snapshots.json"


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT.resolve())).replace("\\", "/")
    except Exception:
        return path.name


def _load_snapshot(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("snapshot baseline path must be a regular file")
    size = int(path.stat().st_size)
    if size < 0 or size > MAX_SNAPSHOT_BYTES:
        raise RuntimeError(f"snapshot baseline too large: {size} bytes")
    doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(doc, dict):
        raise RuntimeError("snapshot baseline must be a JSON object")
    return doc




def _prompt_has_block(prompt: str, open_marker: str, close_marker: str) -> bool:
    return open_marker in prompt and close_marker in prompt


def _validate_prompt_shape(case: dict[str, object], prompt: str) -> list[str]:
    problems: list[str] = []
    expected_blocks = case.get("expected_prompt_blocks")
    if not isinstance(expected_blocks, dict):
        return problems

    block_contract = {
        "protocol": (PROTOCOL_OPEN, PROTOCOL_CLOSE),
        "grounding": (GROUNDING_OPEN, GROUNDING_CLOSE),
    }
    for block_name, markers in block_contract.items():
        if block_name not in expected_blocks:
            continue
        observed = _prompt_has_block(prompt, markers[0], markers[1])
        expected = bool(expected_blocks.get(block_name))
        if observed is not expected:
            state = "present" if observed else "absent"
            problems.append(
                f"case {case['name']}: expected {block_name} block {expected} but observed {state}"
            )
    return problems


def _normalize_case_contract(case: object) -> dict[str, object] | None:
    if not isinstance(case, dict):
        return None
    return {
        "sha256": case.get("sha256"),
        "length": case.get("length"),
        "meta": case.get("meta"),
    }


def _validate_baseline_contract(baseline: dict[str, object], built: dict[str, dict]) -> list[str]:
    problems: list[str] = []
    baseline_schema = baseline.get("schema_version")
    if baseline_schema != SNAPSHOT_SCHEMA_VERSION:
        problems.append(
            f"baseline schema_version mismatch: expected {SNAPSHOT_SCHEMA_VERSION}, got {baseline_schema!r}"
        )

    baseline_cases_obj = baseline.get("cases")
    if not isinstance(baseline_cases_obj, dict):
        problems.append("baseline cases must be a JSON object")
        return problems

    baseline_names = set(str(name) for name in baseline_cases_obj.keys())
    built_names = set(built.keys())
    for name in sorted(built_names - baseline_names):
        problems.append(f"missing baseline case: {name}")
    for name in sorted(baseline_names - built_names):
        problems.append(f"extra baseline case: {name}")

    for name in sorted(built_names & baseline_names):
        observed = _normalize_case_contract(baseline_cases_obj.get(name))
        expected = _normalize_case_contract(built.get(name))
        if observed is None:
            problems.append(f"case {name}: baseline entry must be a JSON object")
            continue
        if observed != expected:
            for field in ("sha256", "length", "meta"):
                if observed.get(field) != expected.get(field):
                    problems.append(f"case {name}: {field} mismatch")
    return problems


def _write_snapshot_json(path: Path, doc: dict) -> None:
    if path.exists():
        st = os.lstat(path)
        if path.is_symlink():
            raise RuntimeError("refusing to overwrite symlinked snapshot baseline")
        if not path.is_file():
            raise RuntimeError("snapshot baseline path is not a regular file")
        if int(getattr(st, "st_nlink", 1)) > 1:
            raise RuntimeError("refusing to overwrite multiply-linked snapshot baseline")

    payload = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}"
    try:
        with open(tmp, "x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    if path.is_symlink():
        raise RuntimeError("snapshot baseline path became a symlink after write")


def main() -> int:
    ap = argparse.ArgumentParser(prog="prompt_snapshot_guard")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--update", action="store_true", help="Update snapshot baseline")
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    repo_root = _REPO_ROOT
    try:
        snap_path = _snapshot_path(repo_root, create_parent=bool(args.update))
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    built: dict[str, dict] = {}
    semantic_problems: list[str] = []
    for c in _cases(repo_root):
        prompt, meta = build_tutor_prompt(c["user_text"], cfg=c["cfg"], turn_index=int(c["turn_index"]))
        case_meta = {
            "protocol_regrounded": bool(meta.protocol_regrounded),
            "grounding_enabled": bool(meta.grounding_enabled),
        }
        expected_meta = dict(c.get("expected_meta") or {})
        for key, expected in expected_meta.items():
            observed = case_meta.get(key)
            if observed is not bool(expected):
                semantic_problems.append(
                    f"case {c['name']}: expected {key}={bool(expected)} but observed {observed}"
                )
        semantic_problems.extend(_validate_prompt_shape(c, prompt))
        built[c["name"]] = {
            "sha256": _sha256(prompt),
            "length": len(prompt),
            "meta": case_meta,
        }

    baseline: dict[str, dict] = {}
    baseline_missing = False
    try:
        baseline = _load_snapshot(snap_path)
        baseline_missing = not snap_path.exists()
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    problems: list[str] = list(semantic_problems)
    if baseline_missing and not args.update:
        problems.append("snapshot baseline missing; re-run with --update to create it intentionally")
    elif baseline and not args.update:
        problems.extend(_validate_baseline_contract(baseline, built))

    overall = "PASS" if not problems else "FAIL"
    updated_baseline = False

    if args.update:
        snap = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cases": built,
        }
        try:
            _write_snapshot_json(snap_path, snap)
            updated_baseline = True
        except Exception as e:
            problems.append(f"baseline write blocked: {e}")
            overall = "FAIL"

    report = {
        "schema_version": "prompt_snapshot_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "overall": overall,
        "baseline_path": _repo_rel(snap_path),
        "cases": built,
        "problems": problems,
        "updated_baseline": updated_baseline,
    }
    write_json((run_dir / "prompt_snapshot_report.json"), report)

    deterministic = bool(not args.update)
    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": args.seed,
            "deterministic": deterministic,
            "outputs": ["prompt_snapshot_report.json", "prompt_snapshot_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL"},
        },
    )
    (run_dir / "prompt_snapshot_summary.md").write_text(
        "\n".join(
            [
                f"# Prompt Snapshot Summary - {overall}",
                "",
                f"- issue: {args.issue}",
                f"- run_id: {run_id}",
                f"- seed: {args.seed}",
                f"- updated_baseline: {updated_baseline}",
                f"- problems: {len(problems)}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"{overall}: wrote outputs to {run_dir}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

