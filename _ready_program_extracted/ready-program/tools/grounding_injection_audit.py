#!/usr/bin/env python3
from __future__ import annotations

"""Grounding injection audit.

Verifies that when local grounding is enabled, the grounding snippets retrieved
match what is injected into the Tutor prompt (markers, labels, and excerpt text).

Exit codes: 0 PASS, 1 FAIL.
"""

import argparse
import json
import os
import random
import re
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

_LABEL_RE = re.compile(r"\[src:([a-zA-Z0-9_\-]+):(\d+)\]")
MAX_LABEL_CHECKS = 4096
_DEFAULT_GROUNDING_DIR = "curriculum"


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _extract_between(text: str, a: str, b: str) -> tuple[str, str | None]:
    t = text or ""
    i = t.find(a)
    if i < 0:
        return "", "missing_open_marker"
    i += len(a)
    j = t.find(b, i)
    if j < 0:
        return "", "missing_close_marker"
    if j < i:
        return "", "invalid_marker_order"
    return t[i:j].strip(), None


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _as_str_list(value) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        s = str(item or "").strip()
        if s:
            out.append(s)
    return out


def _resolve_within(root: Path, rel_path: str) -> Path | None:
    candidate = Path((rel_path or "").strip())
    if not str(candidate) or str(candidate) in {"", "."}:
        return None
    if candidate.is_absolute():
        return None
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except Exception:
        return None
    return resolved


def _normalize_grounding_dir(raw_path: str, *, repo_root: Path) -> tuple[str, Path, str | None]:
    requested = str(raw_path or "").strip()
    fallback_rel = _DEFAULT_GROUNDING_DIR
    fallback_abs = (repo_root.resolve() / fallback_rel).resolve()
    if not requested:
        return fallback_rel, fallback_abs, None

    resolved = _resolve_within(repo_root, requested)
    if resolved is None:
        note = f"invalid grounding_dir override ignored: {requested!r}; using {_DEFAULT_GROUNDING_DIR!r}"
        return fallback_rel, fallback_abs, note

    return resolved.relative_to(repo_root.resolve()).as_posix(), resolved, None


def main() -> int:
    p = argparse.ArgumentParser(prog="grounding_injection_audit")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--turn-index", type=int, default=0)
    p.add_argument("--text", default="uneven fit-up and tack weld spacing")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    from xyzgl.config import XYZGLConfig
    from xyzgl.grounding.prompting import build_grounding
    from xyzgl.prompting import GROUNDING_CLOSE, GROUNDING_OPEN, build_tutor_prompt, normalize_and_clamp_user_text

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    base = XYZGLConfig.from_env()
    requested_grounding_dir = str(base.grounding_dir or "").strip()
    normalized_grounding_dir, gdir, grounding_dir_note = _normalize_grounding_dir(requested_grounding_dir, repo_root=_REPO_ROOT)
    # Force local grounding for this audit (keeps tool deterministic even if env disables grounding).
    cfg = XYZGLConfig(
        tutor_backend=base.tutor_backend,
        mirror_backend=base.mirror_backend,
        enable_mirror=base.enable_mirror,
        tutor_model=base.tutor_model,
        mirror_model=base.mirror_model,
        ollama_host=base.ollama_host,
        protocol_path=base.protocol_path,
        protocol_reground_every=base.protocol_reground_every,
        grounding_mode="local",
        grounding_dir=normalized_grounding_dir,
        grounding_max_snippets=base.grounding_max_snippets,
        grounding_max_chars=base.grounding_max_chars,
        enforce_determinism=base.enforce_determinism,
        max_chars_in=base.max_chars_in,
        max_chars_out=base.max_chars_out,
        llm_backend=base.llm_backend,
    )

    problems: list[str] = []
    notes: list[str] = []
    if grounding_dir_note:
        notes.append(grounding_dir_note)
    effective_query = normalize_and_clamp_user_text(args.text, max_chars=cfg.max_chars_in)
    gtext, gmeta = build_grounding(
        gdir,
        effective_query,
        max_snippets=cfg.grounding_max_snippets,
        max_chars=cfg.grounding_max_chars,
    )
    prompt, pmeta = build_tutor_prompt(effective_query, cfg=cfg, turn_index=args.turn_index)
    injected, marker_err = _extract_between(prompt, GROUNDING_OPEN, GROUNDING_CLOSE)
    direct_snippets = _as_list(_as_dict(gmeta).get("snippets"))
    has_expected_grounding = bool((gtext or "").strip()) or bool(direct_snippets)
    corpus_warnings = _as_str_list(_as_dict(gmeta).get("warnings"))

    if not has_expected_grounding:
        problems.append("grounding requested but no snippets were produced")
    if not pmeta.grounding_enabled and has_expected_grounding:
        problems.append("grounding_enabled should be true")
    if marker_err and has_expected_grounding:
        problems.append(f"grounding marker parse error: {marker_err}")
    if has_expected_grounding and (gtext or "").strip() != (injected or "").strip():
        problems.append("injected grounding text does not match build_grounding output")
    for warning in corpus_warnings:
        problems.append(f"corpus warning: {warning}")

    injected_labels = {f"{m.group(1)}:{m.group(2)}" for m in _LABEL_RE.finditer(injected or "")}
    label_count = 0
    missing_labels: list[str] = []
    for m in _LABEL_RE.finditer(gtext or ""):
        label_count += 1
        if label_count > MAX_LABEL_CHECKS:
            problems.append(f"too many labels to verify (> {MAX_LABEL_CHECKS}); review grounding limits")
            break
        key = f"{m.group(1)}:{m.group(2)}"
        if key not in injected_labels and len(missing_labels) < 20:
            missing_labels.append(key)
    for key in missing_labels:
        problems.append(f"missing label in injected text: [src:{key}]")

    used = direct_snippets
    if used and label_count <= MAX_LABEL_CHECKS and label_count != len(used):
        problems.append(f"label/snippet count mismatch: labels={label_count} snippets={len(used)}")

    ok = not problems
    report = {
        "schema_version": "grounding_audit_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "turn_index": args.turn_index,
        "requested_grounding_dir": requested_grounding_dir,
        "grounding_dir": cfg.grounding_dir,
        "grounding_dir_abs": str(gdir),
        "query": args.text,
        "effective_query": effective_query,
        "snippets": used,
        "pass": ok,
        "problems": problems,
        "notes": notes,
    }
    write_json((run_dir / "grounding_audit_report.json"), report)

    summary = [
        "# Grounding Injection Audit",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- grounding_dir: `{cfg.grounding_dir}`",
        "",
    ]
    if notes:
        summary.extend([f"- note: {note}" for note in notes])
        summary.append("")
    if ok:
        summary.append("- ✅ PASS")
    else:
        summary.append("- ❌ FAIL")
        summary.extend([f"  - {p}" for p in problems])
    (run_dir / "grounding_audit_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["grounding_audit_report.json", "grounding_audit_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
