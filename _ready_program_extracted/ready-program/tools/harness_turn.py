#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

# Keep zip-distributed repos clean (avoid creating __pycache__/ during harness runs)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, invalid_runs_override_reason, make_run_id

# Ensure repo-root is importable when this script is executed from tools/.
# When you run `python tools/harness_turn.py`, Python sets sys.path[0] to
# the script folder (tools/), so `import xyzgl` would fail without this.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from witness.core import WitnessCore
from xyzgl import router as _router_module
from xyzgl.config import XYZGLConfig
from xyzgl.prompting import prompt_user_block_text, render_prompt_user_block
from xyzgl.router import _sanitize_obj as _router_sanitize_obj
from xyzgl.router import _sanitize_text as _router_sanitize_text
from xyzgl.router import route_turn

MAX_ARTIFACT_INPUT_CHARS = 8_000
MAX_ARTIFACT_REPLY_CHARS = 12_000
MAX_ARTIFACT_BACKEND_ERROR_CHARS = 2_000
MAX_ARTIFACT_MIRROR_META_CHARS = 4_000
MAX_TURN_SUMMARY_CHARS = 16_000
_SUMMARY_UNSAFE_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_EXTRA_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [A-Z0-9 ][A-Z0-9 -]*PRIVATE KEY(?: BLOCK)?-----.*?-----END [A-Z0-9 ][A-Z0-9 -]*PRIVATE KEY(?: BLOCK)?-----", flags=re.IGNORECASE | re.DOTALL), "<redacted-private-key>"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "<redacted>"),
    (re.compile(r"\bgh(?:p|o|s|u|r)_[A-Za-z0-9_]{20,}\b"), "<redacted>"),
    (re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b"), "<redacted>"),
    (re.compile(r"\b(?:sk_live_[A-Za-z0-9\-_]{20,}|sk-ant-[A-Za-z0-9\-_]{20,})\b"), "<redacted>"),
    (re.compile(r"\b(?:hf_[A-Za-z0-9\-_]{20,}|npm_[A-Za-z0-9\-_]{20,})\b"), "<redacted>"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "<redacted>"),
    (re.compile(r"\bxox(?:[aboprst]|x[a-z])-[A-Za-z0-9-]{10,}\b"), "<redacted>"),
    (re.compile(r"\bxapp-\d+-[A-Za-z0-9-]{10,}\b"), "<redacted>"),
    (re.compile(r"\bya29\.[A-Za-z0-9\-_]+\b"), "<redacted>"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<redacted-ssn>"),
    (re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b"), "<redacted-sin>"),
)


def _run_id() -> str:
    return make_run_id()


def _truncate_text(value: object, *, max_chars: int) -> str:
    text = str(value or "")
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"


def _utf8_safe_text(value: object) -> str:
    text = str(value or "")
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _apply_extra_secret_redactions(text: str) -> str:
    out = _utf8_safe_text(text)
    for rx, replacement in _EXTRA_SECRET_PATTERNS:
        out = rx.sub(replacement, out)
    return out


def _artifact_sanitize_text(value: object, *, limit: int) -> str:
    text = _apply_extra_secret_redactions(_utf8_safe_text(value))
    return _router_sanitize_text(text, limit=max(1, int(limit)))


def _artifact_preserve_text(value: object, *, limit: int) -> str:
    text = _apply_extra_secret_redactions(_utf8_safe_text(value))
    text = _router_module._clamp(text, max(1, int(limit)))
    text = _router_module._GENERIC_SECRET_RE.sub("<redacted>", text)
    text = _router_module._QUERY_SECRET_RE.sub(r"\1<redacted>", text)
    text = _router_module._HEADER_SECRET_RE.sub(lambda m: f"{m.group(1)}: <redacted>", text)
    return text


def _artifact_sanitize_key(value: object) -> str:
    return _utf8_safe_text(value)


def _artifact_sanitize_obj(value):
    base = _router_sanitize_obj(value)
    if isinstance(base, dict):
        return {_artifact_sanitize_key(k): _artifact_sanitize_obj(v) for k, v in base.items()}
    if isinstance(base, list):
        return [_artifact_sanitize_obj(v) for v in base]
    if isinstance(base, tuple):
        return [_artifact_sanitize_obj(v) for v in base]
    if isinstance(base, set):
        return [_artifact_sanitize_obj(v) for v in sorted(base, key=lambda x: repr(x))]
    if isinstance(base, str):
        return _artifact_sanitize_text(base, limit=1024)
    return base


def _artifact_result(result: dict) -> dict:
    out = _artifact_sanitize_obj(dict(result or {}))
    out["input"] = _truncate_text(_utf8_safe_text(out.get("input")), max_chars=MAX_ARTIFACT_INPUT_CHARS)
    out["reply"] = _truncate_text(_utf8_safe_text(out.get("reply")), max_chars=MAX_ARTIFACT_REPLY_CHARS)
    if "backend_error" in out:
        out["backend_error"] = _truncate_text(_utf8_safe_text(out.get("backend_error")), max_chars=MAX_ARTIFACT_BACKEND_ERROR_CHARS)
    out["artifact_trimmed"] = True
    return out


def _input_lineage(result: dict, raw_text: object) -> tuple[str, str, str, str]:
    raw_cli = _artifact_preserve_text(raw_text, limit=MAX_ARTIFACT_INPUT_CHARS)
    routed_input = _artifact_sanitize_text(result.get("input") or raw_text, limit=MAX_ARTIFACT_INPUT_CHARS)
    prompt_meta = result.get("prompt_meta") or {}
    if not isinstance(prompt_meta, dict):
        prompt_meta = {}
    prompt_user = prompt_meta.get("user_block_text")
    if prompt_user in (None, ""):
        prompt_user = prompt_user_block_text(routed_input, max_chars=MAX_ARTIFACT_INPUT_CHARS)
    prompt_user = _artifact_sanitize_text(prompt_user, limit=MAX_ARTIFACT_INPUT_CHARS)
    prompt_user_rendered = prompt_meta.get("user_block_rendered")
    if prompt_user_rendered in (None, ""):
        prompt_user_rendered = render_prompt_user_block(routed_input, max_chars=MAX_ARTIFACT_INPUT_CHARS)
    prompt_user_rendered = _artifact_sanitize_text(prompt_user_rendered, limit=MAX_ARTIFACT_INPUT_CHARS)
    return raw_cli, routed_input, prompt_user, prompt_user_rendered


def _summary_artifact_text(value: object, *, max_chars: int) -> str:
    text = _artifact_sanitize_text(value, limit=max_chars)
    text = _SUMMARY_UNSAFE_CONTROL_RE.sub("", text)
    return _truncate_text(text, max_chars=max_chars)


def _summary_preserve_text(value: object, *, max_chars: int) -> str:
    text = _artifact_preserve_text(value, limit=max_chars)
    text = _SUMMARY_UNSAFE_CONTROL_RE.sub("", text)
    return _truncate_text(text, max_chars=max_chars)


def _summary_json_artifact_text(value: object, *, max_chars: int) -> str:
    text = json.dumps(_artifact_sanitize_obj(value), ensure_ascii=False, indent=2, sort_keys=True)
    return _summary_artifact_text(text, max_chars=max_chars)


def _md_fenced(text: str) -> str:
    t = _utf8_safe_text(text)
    # Keep markdown fences stable even if input contains backticks.
    t = t.replace("```", "``\\`")
    return f"```text\n{t}\n```"


def _truncate_visible_text(text: str, *, max_chars: int) -> str:
    marker = "...<truncated>"
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker):
        return marker[:max_chars]
    return text[: max_chars - len(marker)] + marker


def _fit_summary_section(title: str, body_text: str, *, remaining_chars: int) -> str:
    section_prefix = f"\n\n## {title}\n\n"
    minimum_fenced = _md_fenced("")
    if remaining_chars <= len(section_prefix) + len(minimum_fenced):
        return ""

    full_block = section_prefix + _md_fenced(body_text)
    if len(full_block) <= remaining_chars:
        return full_block

    lo = 0
    hi = len(body_text)
    best = section_prefix + _md_fenced(_truncate_visible_text(body_text, max_chars=1))
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = section_prefix + _md_fenced(_truncate_visible_text(body_text, max_chars=mid))
        if len(candidate) <= remaining_chars:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _render_turn_summary(*, args: argparse.Namespace, run_id: str, overall: str, sections: list[tuple[str, str]]) -> str:
    summary_md = (
        f"# Turn Summary — {overall}\n\n"
        f"- issue: `{args.issue}`\n"
        f"- seed: `{args.seed}`\n"
        f"- run_id: `{run_id}`\n"
        f"- overall: `{overall}`\n"
    )
    omitted_sections = 0
    for idx, (title, body_text) in enumerate(sections):
        remaining_chars = MAX_TURN_SUMMARY_CHARS - len(summary_md)
        if remaining_chars <= 0:
            omitted_sections = len(sections) - idx
            break
        section_md = _fit_summary_section(title, body_text, remaining_chars=remaining_chars)
        if not section_md:
            omitted_sections = len(sections) - idx
            break
        summary_md += section_md
        if len(section_md) < len(f"\n\n## {title}\n\n" + _md_fenced(body_text)):
            omitted_sections = len(sections) - idx - 1
            break
    if omitted_sections > 0:
        note = f"\n\n_Note: {omitted_sections} additional summary section(s) omitted due to size cap._\n"
        remaining_chars = MAX_TURN_SUMMARY_CHARS - len(summary_md)
        if remaining_chars > 0:
            summary_md += note[:remaining_chars]
    return summary_md


def _contract_fail_result(result: dict, *, cfg: XYZGLConfig, args: argparse.Namespace, error_message: str) -> dict:
    base = dict(result or {})
    backend = _utf8_safe_text(base.get("backend") or "<error>")
    requested_backend = _utf8_safe_text(base.get("requested_backend") or cfg.tutor_backend or "<error>")
    effective_backend = _utf8_safe_text(base.get("effective_backend") or backend)
    fail = {
        **base,
        "config": _artifact_sanitize_obj(base.get("config") or asdict(cfg)),
        "input": _utf8_safe_text(base.get("input") or args.text),
        "seed": base.get("seed", args.seed),
        "turn_index": base.get("turn_index", 0),
        "reply": "",
        "backend": backend,
        "requested_backend": requested_backend,
        "effective_backend": effective_backend,
        "backend_error": error_message,
        "exception_type": "BackendContractError",
        "exception_message": error_message,
    }
    return fail


@contextmanager
def _env_patch(pairs: dict[str, str | None]):
    old = {k: os.environ.get(k) for k in pairs}
    try:
        for k, v in pairs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _write_turn_outputs(*, run_dir: Path, args: argparse.Namespace, run_id: str, overall: str, artifact_result: dict) -> None:
    wc = WitnessCore()
    event = wc.make_event(args.issue, {"turn_result": artifact_result})
    wc.write_event_json(event, str(run_dir / "turn_report.json"))

    raw_cli_input = _utf8_safe_text(artifact_result.get("input_raw") or artifact_result.get("input") or args.text)
    routed_input = _utf8_safe_text(artifact_result.get("input_routed") or artifact_result.get("input") or args.text)
    prompt_user_block = _utf8_safe_text(artifact_result.get("prompt_user_block") or routed_input)
    prompt_user_block_rendered = _utf8_safe_text(artifact_result.get("prompt_user_block_rendered") or prompt_user_block)

    summary_raw_cli_input = _summary_preserve_text(raw_cli_input, max_chars=MAX_ARTIFACT_INPUT_CHARS)
    summary_routed_input = _summary_artifact_text(routed_input, max_chars=MAX_ARTIFACT_INPUT_CHARS)
    summary_prompt_user_block = _summary_artifact_text(prompt_user_block_rendered, max_chars=MAX_ARTIFACT_INPUT_CHARS)
    summary_reply = _summary_artifact_text(artifact_result.get("reply") or "", max_chars=MAX_ARTIFACT_REPLY_CHARS)
    summary_sections: list[tuple[str, str]] = [
        ("Raw CLI Input", summary_raw_cli_input),
        ("Routed Input", summary_routed_input),
        ("Prompt-Facing User Block", summary_prompt_user_block),
        ("Reply", summary_reply),
    ]
    mirror_prediction = artifact_result.get("mirror_prediction")
    if mirror_prediction is not None:
        summary_mirror_prediction = _summary_artifact_text(mirror_prediction, max_chars=MAX_ARTIFACT_REPLY_CHARS)
        summary_sections.append(("Mirror Prediction", summary_mirror_prediction))

    mirror_meta = artifact_result.get("mirror_meta")
    if mirror_meta is not None:
        summary_mirror_meta = _summary_json_artifact_text(mirror_meta, max_chars=MAX_ARTIFACT_MIRROR_META_CHARS)
        summary_sections.append(("Mirror Metadata", summary_mirror_meta))

    backend_error = artifact_result.get("backend_error")
    if backend_error:
        summary_backend_error = _summary_artifact_text(backend_error, max_chars=MAX_ARTIFACT_BACKEND_ERROR_CHARS)
        summary_sections.append(("Backend Error", summary_backend_error))
    summary_md = _render_turn_summary(args=args, run_id=run_id, overall=overall, sections=summary_sections)
    (run_dir / "turn_summary.md").write_text(summary_md, encoding="utf-8", errors="replace")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["turn_report.json", "turn_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)


def _best_effort_failure_artifact(*, run_dir: Path, args: argparse.Namespace, cfg: XYZGLConfig, run_id: str, original_result: dict | None, exc: Exception) -> None:
    message = _utf8_safe_text(f"artifact_emit_error: {type(exc).__name__}: {exc}")
    fail_result = _contract_fail_result(original_result or {}, cfg=cfg, args=args, error_message=message)
    artifact_result = _artifact_result(fail_result)
    raw_cli_input, routed_input, prompt_user_block, prompt_user_block_rendered = _input_lineage({}, args.text)
    artifact_result["input"] = routed_input
    artifact_result["input_raw"] = raw_cli_input
    artifact_result["input_routed"] = routed_input
    artifact_result["prompt_user_block"] = prompt_user_block
    artifact_result["prompt_user_block_rendered"] = prompt_user_block_rendered
    prompt_meta = artifact_result.get("prompt_meta")
    if isinstance(prompt_meta, dict):
        prompt_meta["user_block_text"] = prompt_user_block
        prompt_meta["user_block_rendered"] = prompt_user_block_rendered
    _write_turn_outputs(run_dir=run_dir, args=args, run_id=run_id, overall="FAIL", artifact_result=artifact_result)


def _fault_mode_from_env() -> str:
    return _utf8_safe_text(os.getenv("DAEDALUS_FAULT_MODE") or "").strip().lower()


def _requested_fault_empty_replied_via_fallback(result: dict, *, cfg: XYZGLConfig) -> bool:
    requested_backend = _utf8_safe_text(result.get("requested_backend") or cfg.tutor_backend or "")
    effective_backend = _utf8_safe_text(result.get("effective_backend") or result.get("backend") or "")
    if requested_backend.lower() != "fault":
        return False
    if _fault_mode_from_env() != "empty":
        return False
    return bool(effective_backend) and effective_backend.lower() != requested_backend.lower()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--text", default="fit-up is uneven, should I keep tacking?")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    override_error = invalid_runs_override_reason()
    if override_error:
        print(f"INCOMPLETE: {override_error}")
        return 2

    random.seed(args.seed)

    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    cfg = XYZGLConfig.from_env()
    exit_code = 0
    overall = "PASS"

    # Run the turn
    try:
        with _env_patch({"GWEN_DISABLED": "1"}):
            result = route_turn(args.text, seed=args.seed, cfg=cfg)
        if _utf8_safe_text(result.get("reply") or "") == "" or _requested_fault_empty_replied_via_fallback(result, cfg=cfg):
            exit_code = 1
            overall = "FAIL"
            result = _contract_fail_result(
                result,
                cfg=cfg,
                args=args,
                error_message="backend_contract_error: empty tutor reply",
            )
    except Exception as e:
        exit_code = 1
        overall = "FAIL"
        result = {
            "config": asdict(cfg),
            "input": _utf8_safe_text(args.text),
            "seed": args.seed,
            "turn_index": 0,
            "reply": "",
            "backend": "<error>",
            "requested_backend": cfg.tutor_backend,
            "effective_backend": "<error>",
            "backend_error": f"{type(e).__name__}: {e}",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
        }
    artifact_result = _artifact_result(result)
    raw_cli_input, routed_input, prompt_user_block, prompt_user_block_rendered = _input_lineage(result, args.text)
    artifact_result["input"] = routed_input
    artifact_result["input_raw"] = raw_cli_input
    artifact_result["input_routed"] = routed_input
    artifact_result["prompt_user_block"] = prompt_user_block
    artifact_result["prompt_user_block_rendered"] = prompt_user_block_rendered
    prompt_meta = artifact_result.get("prompt_meta")
    if isinstance(prompt_meta, dict):
        prompt_meta["user_block_text"] = prompt_user_block
        prompt_meta["user_block_rendered"] = prompt_user_block_rendered

    try:
        _write_turn_outputs(
            run_dir=run_dir,
            args=args,
            run_id=run_id,
            overall=overall,
            artifact_result=artifact_result,
        )
    except Exception as e:
        exit_code = 1
        overall = "FAIL"
        _best_effort_failure_artifact(
            run_dir=run_dir,
            args=args,
            cfg=cfg,
            run_id=run_id,
            original_result=result if isinstance(result, dict) else None,
            exc=e,
        )

    print(f"{overall}: wrote outputs to {run_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
