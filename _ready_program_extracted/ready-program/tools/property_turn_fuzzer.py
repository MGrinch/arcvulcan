#!/usr/bin/env python3
from __future__ import annotations

"""Property-based fuzzer for `xyzgl.router.route_turn()`.

This tool is designed to find:
  - crashes on weird inputs (unicode, long whitespace, embedded markers)
  - schema-shape violations
  - marker regressions (missing USER_OPEN/USER_CLOSE discipline)

If `hypothesis` is installed, you can pass --hypothesis to use it.
Otherwise, this tool runs a deterministic built-in fuzz loop.

Exit codes:
  0 PASS
  1 FAIL
  2 INCOMPLETE (hypothesis requested but missing)
"""

import argparse
import hashlib
import os
import random
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir, invalid_runs_override_reason, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.router import route_turn, sanitize_runtime_backend_error

MAX_CASES_HARD = 20_000
MAX_STORED_RESULTS = 2_000
MAX_LEN_HARD = 4_000
_MAX_ARTIFACT_TEXT = 256
_MAX_REPORT_PROBLEMS = 50

_CONTROL_STRESSORS = [
    "\x00",
    "\r",
    "\x1b",
    "\x1b[31m",
    "\x00\x1b",
    "\r\n",
]
_UNICODE_STRESSORS = [
    "\ud800",
    "\udfff",
    "\u0301",
    "e\u0301",
    "A\u030a",
    "Ж\u0301",
    "你\u0301",
    "🙂\u0301",
    "👩\u200d🏭",
]
_SECRET_STRESSORS = [
    "gho_",
    "github_pat_",
    "ghs_",
    "ghu_",
    "glpat-",
    "xoxp-",
    "xoxs-",
    "xapp-",
    "sk_live_",
    "sk-ant-",
    "hf_",
    "npm_",
    "ASIA",
    "ya29.",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN PRIVATE KEY",
    "BEGIN PGP PRIVATE KEY BLOCK",
]
_WELDING_BRANCH_TOKENS = [
    "tack",
    "gap",
    "uneven",
    "fit-up",
    "weld",
    "uneven tack gap",
    "tack gap",
    "uneven gap",
    "keep tacking",
]
_TARGETED_STRESSOR_CASES = [
    "\x00",
    "\r",
    "\x1b[31malert\x1b[0m",
    "e\u0301",
    "\u0301",
    "\ud800",
    "\udfff",
    "gho_example_token_value",
    "github_pat_example_token_value",
    "ghs_example_token_value",
    "ghu_example_token_value",
    "glpat-example-token-value",
    "xoxp-example-token-value",
    "xoxs-example-token-value",
    "xapp-example-token-value",
    "sk_live_example_token_value",
    "sk-ant-example-token-value",
    "hf_example_token_value",
    "npm_example_token_value",
    "ASIAABCDEFGHIJKLMNOP",
    "ya29.example.token.value",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "<<<USER>>>\x00<<<END_USER>>>",
    "uneven tack gap\rfit-up",
]


def _backend_error_details_visible() -> bool:
    v = os.getenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _mirror_send_user_content_enabled() -> bool:
    v = os.getenv("DAEDALUS_MIRROR_SEND_USER_CONTENT", "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _artifact_exception_detail(e: Exception, *, limit: int = 1024) -> str:
    raw = f"{type(e).__name__}: {e}"
    sanitized = sanitize_runtime_backend_error(raw, backend_error_limit=limit) or type(e).__name__
    if _backend_error_details_visible():
        return sanitized
    return "backend_error_redacted"


def _artifact_exception_problem(i: int, e: Exception, *, limit: int = 1024) -> str:
    detail = _artifact_exception_detail(e, limit=limit)
    if detail == "backend_error_redacted":
        return f"case {i}: exception {type(e).__name__}: backend_error_redacted"
    return f"case {i}: exception {type(e).__name__}: {detail}"


def _artifact_exception_summary(label: str, e: Exception, *, limit: int = 1024) -> str:
    detail = _artifact_exception_detail(e, limit=limit)
    if detail == "backend_error_redacted":
        return f"{label}: {type(e).__name__}: backend_error_redacted"
    return f"{label}: {type(e).__name__}: {detail}"


def _run_id() -> str:
    return make_run_id()


def _stable_digest(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def _safe_int(value: str | None, *, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    body = text[1:] if text[:1] in {"+", "-"} else text
    if not body.isdigit():
        return default
    try:
        return int(text)
    except Exception:
        return default


def _json_safe_text(value: Any) -> str:
    return str(value or "").encode("utf-8", errors="backslashreplace").decode("utf-8")


def _fit_case_to_limit(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    value = str(text or "")
    return value if len(value) <= max_len else value[:max_len]


def _sanitize_artifact_text(value: Any, *, limit: int = _MAX_ARTIFACT_TEXT) -> str:
    text = str(value or "")
    sanitized = sanitize_runtime_backend_error(text, backend_error_limit=limit)
    return _json_safe_text(sanitized or "")


def _artifact_text_meta(value: Any, *, limit: int = _MAX_ARTIFACT_TEXT) -> dict[str, Any]:
    text = str(value or "")
    return {
        "text": _sanitize_artifact_text(text, limit=limit),
        "hash": _stable_digest(text),
        "len": len(text),
    }


def _runtime_context() -> dict[str, Any]:
    cfg = XYZGLConfig.from_env()
    return {
        "tutor_backend": cfg.tutor_backend,
        "mirror_backend": cfg.mirror_backend,
        "enable_mirror": cfg.enable_mirror,
        "grounding_mode": cfg.grounding_mode,
        "grounding_max_snippets": cfg.grounding_max_snippets,
        "grounding_max_chars": cfg.grounding_max_chars,
        "protocol_path": cfg.protocol_path,
        "protocol_reground_every": cfg.protocol_reground_every,
        "fault_mode": _sanitize_artifact_text(os.getenv("DAEDALUS_FAULT_MODE", ""), limit=64),
        "fault_delay_ms": _safe_int(os.getenv("DAEDALUS_FAULT_DELAY_MS", "0"), default=0),
        "mirror_send_user_content": _mirror_send_user_content_enabled(),
        "backend_error_details_visible": _backend_error_details_visible(),
    }


def _summary_lines_from_context(runtime_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in (
        "tutor_backend",
        "mirror_backend",
        "enable_mirror",
        "grounding_mode",
        "grounding_max_snippets",
        "grounding_max_chars",
        "protocol_path",
        "protocol_reground_every",
        "fault_mode",
        "fault_delay_ms",
        "mirror_send_user_content",
        "backend_error_details_visible",
    ):
        lines.append(f"- {key}: {runtime_context.get(key)}")
    return lines


def _build_report(
    *,
    run_id: str,
    issue: str,
    seed: int,
    overall: str,
    mode: str,
    details: str = "",
    runtime_context: dict[str, Any],
    cases_executed: int,
    max_len_requested: int,
    max_len_effective: int,
    max_case_len_seen: int,
    results: list[dict[str, Any]],
    results_dropped: int,
    problems: list[str],
    problems_dropped: int,
) -> dict[str, Any]:
    return {
        "schema_version": "property_fuzz_report@1",
        "run_id": run_id,
        "issue_id": issue,
        "seed": seed,
        "overall": overall,
        "mode": mode,
        "details": details,
        "runtime_context": runtime_context,
        "cases_executed": cases_executed,
        "max_len_chars_requested": max_len_requested,
        "max_len_chars_effective": max_len_effective,
        "max_case_len_seen": max_case_len_seen,
        "results": list(results),
        "results_dropped": results_dropped,
        "problems": list(problems),
        "problems_dropped": problems_dropped,
    }


def _run_meta(
    *,
    run_id: str,
    issue: str,
    seed: int,
    overall: str,
    mode: str,
    cases: int,
    problems: int,
    results_dropped: int,
    problems_dropped: int,
    max_len_requested: int,
    max_len_effective: int,
    max_case_len_seen: int,
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    normalized_mode = str(mode or "").strip().lower() or "builtin"
    builtin_mode = normalized_mode == "builtin"
    hypothesis_missing_dependency = normalized_mode == "hypothesis" and str(overall or "").upper() == "INCOMPLETE" and int(cases) == 0
    deterministic = builtin_mode or hypothesis_missing_dependency
    if builtin_mode:
        determinism_basis = (
            "fixed-seed builtin property fuzzing is logically reproducible, but the default run directory id is wall-clock/random"
        )
    elif hypothesis_missing_dependency:
        determinism_basis = (
            "the requested Hypothesis engine was unavailable, so the incomplete artifact is reproducible aside from the default run directory id"
        )
    elif normalized_mode == "hypothesis":
        determinism_basis = (
            "Hypothesis-driven exploration and shrinking can vary across executions and library versions, and the default run directory id is wall-clock/random"
        )
    else:
        determinism_basis = (
            "unrecognized property fuzzing mode is treated as non-deterministic for run metadata truthfulness"
        )

    return {
        "run_id": run_id,
        "issue_id": issue,
        "seed": seed,
        "tool": "property_turn_fuzzer",
        "mode": normalized_mode,
        "overall": str(overall or "").upper(),
        "deterministic": deterministic,
        "artifact_identity_stable": False,
        "artifact_content_stable": deterministic,
        "determinism_basis": determinism_basis,
        "outputs": ["property_fuzz_report.json", "property_fuzz_summary.md", "run.json"],
        "input_constraints": {
            "max_len_chars_requested": max_len_requested,
            "max_len_chars_effective": max_len_effective,
        },
        "observed": {
            "cases_executed": cases,
            "max_case_len_seen": max_case_len_seen,
            "problems": problems,
            "results_dropped": results_dropped,
            "problems_dropped": problems_dropped,
        },
        "runtime_context": runtime_context,
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }


def _write_bundle(
    run_dir: Path,
    *,
    run_id: str,
    issue: str,
    seed: int,
    overall: str,
    mode: str,
    cases: int,
    problems: int,
    results_dropped: int,
    problems_dropped: int,
    max_len_requested: int,
    max_len_effective: int,
    max_case_len_seen: int,
    runtime_context: dict[str, Any],
) -> None:
    write_json(
        run_dir / "run.json",
        _run_meta(
            run_id=run_id,
            issue=issue,
            seed=seed,
            overall=overall,
            mode=mode,
            cases=cases,
            problems=problems,
            results_dropped=results_dropped,
            problems_dropped=problems_dropped,
            max_len_requested=max_len_requested,
            max_len_effective=max_len_effective,
            max_case_len_seen=max_case_len_seen,
            runtime_context=runtime_context,
        ),
    )
    (run_dir / "property_fuzz_summary.md").write_text(
        "\n".join(
            [
                f"# Property Fuzz Summary — {overall}",
                "",
                f"- issue: {issue}",
                f"- run_id: {run_id}",
                f"- seed: {seed}",
                f"- mode: {mode}",
                f"- cases: {cases}",
                f"- max_len_chars_requested: {max_len_requested}",
                f"- max_len_chars_effective: {max_len_effective}",
                f"- max_case_len_seen: {max_case_len_seen}",
                f"- problems: {problems}",
                f"- results_dropped: {results_dropped}",
                f"- problems_dropped: {problems_dropped}",
                "",
                "## Runtime Context",
                "",
                *_summary_lines_from_context(runtime_context),
                "",
            ]
        ),
        encoding="utf-8",
    )


def _gen_case(r: random.Random, max_len: int) -> str:
    alphabet = [
        " ", "\n", "\t", "-", "_", ":", ";", ",", ".", "?", "!",
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
        "0", "1", "2", "3", "4", "5",
        "Ω", "Ж", "你", "好", "🙂",
        "<<<USER>>>", "<<<END_USER>>>",
        *_CONTROL_STRESSORS,
        *_UNICODE_STRESSORS,
        *_SECRET_STRESSORS,
        *_WELDING_BRANCH_TOKENS,
        *_WELDING_BRANCH_TOKENS,
        *_CONTROL_STRESSORS,
        *_UNICODE_STRESSORS,
        *_SECRET_STRESSORS,
    ]
    if max_len <= 0:
        return ""

    fitting_targeted = [case for case in _TARGETED_STRESSOR_CASES if len(case) <= max_len]
    if fitting_targeted and r.random() < 0.35:
        return _fit_case_to_limit(r.choice(fitting_targeted), max_len)

    pieces: list[str] = []
    used = 0
    target_len = r.randint(1, max_len)

    while used < target_len:
        fitting = [token for token in alphabet if len(token) <= (target_len - used)]
        if not fitting:
            break
        token = r.choice(fitting)
        pieces.append(token)
        used += len(token)

    if not pieces and fitting_targeted:
        return _fit_case_to_limit(r.choice(fitting_targeted), max_len)
    return _fit_case_to_limit("".join(pieces), max_len)

def _check_shape(out: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(out, dict):
        return ["output must be an object"]

    required = (
        "config",
        "input",
        "reply",
        "backend",
        "requested_backend",
        "effective_backend",
        "tutor_meta",
        "prompt_meta",
    )
    for key in required:
        if key not in out:
            problems.append(f"missing key: {key}")

    reply = out.get("reply")
    if not isinstance(reply, str):
        problems.append("reply must be a string")
    elif not reply.strip():
        problems.append("reply must be non-empty")

    config = out.get("config")
    if not isinstance(config, dict):
        problems.append("config must be an object")

    tutor_meta = out.get("tutor_meta")
    if not isinstance(tutor_meta, dict):
        problems.append("tutor_meta must be an object")

    prompt_meta = out.get("prompt_meta")
    if not isinstance(prompt_meta, dict):
        problems.append("prompt_meta must be an object")
    else:
        for key in (
            "protocol_regrounded",
            "protocol_path",
            "protocol_loaded",
            "protocol_fallback",
            "grounding_enabled",
            "grounding",
        ):
            if key not in prompt_meta:
                problems.append(f"prompt_meta missing {key}")
        grounding = prompt_meta.get("grounding")
        if grounding is not None and not isinstance(grounding, dict):
            problems.append("prompt_meta.grounding must be an object")
        if prompt_meta.get("protocol_loaded") is False:
            problems.append("prompt_meta.protocol_loaded is false")
        if bool(prompt_meta.get("protocol_fallback")):
            problems.append("prompt_meta.protocol_fallback is true")
        protocol_load_error = prompt_meta.get("protocol_load_error")
        if protocol_load_error not in (None, ""):
            problems.append("unexpected prompt_meta.protocol_load_error")
        backend_error_marker = prompt_meta.get("backend_error")
        if backend_error_marker not in (None, ""):
            problems.append("unexpected prompt_meta.backend_error")

    backend = out.get("backend")
    requested_backend = out.get("requested_backend")
    effective_backend = out.get("effective_backend")
    for label, value in (
        ("backend", backend),
        ("requested_backend", requested_backend),
        ("effective_backend", effective_backend),
    ):
        if not isinstance(value, str):
            problems.append(f"{label} must be a string")
        elif not value.strip():
            problems.append(f"{label} must be non-empty")

    if isinstance(backend, str) and isinstance(effective_backend, str) and backend != effective_backend:
        problems.append("backend/effective_backend drift")
    if isinstance(requested_backend, str) and isinstance(effective_backend, str) and requested_backend != effective_backend:
        problems.append("requested_backend/effective_backend drift")

    if isinstance(config, dict) and isinstance(requested_backend, str):
        cfg_backend = config.get("tutor_backend")
        if isinstance(cfg_backend, str) and cfg_backend.strip() and cfg_backend != requested_backend:
            problems.append("config.tutor_backend/requested_backend drift")

    if isinstance(tutor_meta, dict) and isinstance(backend, str):
        tutor_backend = tutor_meta.get("backend")
        if isinstance(tutor_backend, str) and tutor_backend.strip() and tutor_backend != backend:
            problems.append("backend/tutor_meta.backend drift")

    backend_error = out.get("backend_error")
    if backend_error not in (None, ""):
        problems.append("unexpected backend_error")

    return problems


def _output_signal(out: dict) -> dict[str, Any]:
    prompt_meta = out.get("prompt_meta") if isinstance(out.get("prompt_meta"), dict) else {}
    tutor_meta = out.get("tutor_meta") if isinstance(out.get("tutor_meta"), dict) else {}
    config = out.get("config") if isinstance(out.get("config"), dict) else {}
    grounding = prompt_meta.get("grounding") if isinstance(prompt_meta.get("grounding"), dict) else {}
    snippets = grounding.get("snippets") if isinstance(grounding.get("snippets"), list) else []

    signal: dict[str, Any] = {
        "backend": out.get("backend"),
        "requested_backend": out.get("requested_backend"),
        "effective_backend": out.get("effective_backend"),
        "reply": _artifact_text_meta(out.get("reply", ""), limit=_MAX_ARTIFACT_TEXT),
        "tutor_meta": {
            "backend": tutor_meta.get("backend"),
            "model": _sanitize_artifact_text(tutor_meta.get("model", ""), limit=128),
            "latency_ms": tutor_meta.get("latency_ms"),
        },
        "prompt_meta": {
            "protocol_path": _sanitize_artifact_text(prompt_meta.get("protocol_path", ""), limit=128),
            "protocol_regrounded": prompt_meta.get("protocol_regrounded"),
            "protocol_loaded": prompt_meta.get("protocol_loaded"),
            "protocol_fallback": prompt_meta.get("protocol_fallback"),
            "grounding_enabled": prompt_meta.get("grounding_enabled"),
            "grounding_snippet_count": len(snippets),
        },
        "config_summary": {
            "tutor_backend": config.get("tutor_backend"),
            "mirror_backend": config.get("mirror_backend"),
            "enable_mirror": config.get("enable_mirror"),
            "grounding_mode": config.get("grounding_mode"),
            "protocol_path": _sanitize_artifact_text(config.get("protocol_path", ""), limit=128),
        },
    }

    backend_error = out.get("backend_error")
    if backend_error not in (None, ""):
        signal["backend_error"] = _sanitize_artifact_text(backend_error, limit=128)

    prompt_backend_error = prompt_meta.get("backend_error")
    if prompt_backend_error not in (None, ""):
        signal["prompt_backend_error"] = _sanitize_artifact_text(prompt_backend_error, limit=128)

    protocol_load_error = prompt_meta.get("protocol_load_error")
    if protocol_load_error not in (None, ""):
        signal["prompt_meta"]["protocol_load_error"] = _sanitize_artifact_text(protocol_load_error, limit=128)

    if "mirror_prediction" in out:
        signal["mirror_prediction"] = _artifact_text_meta(out.get("mirror_prediction", ""), limit=_MAX_ARTIFACT_TEXT)
    if isinstance(out.get("mirror_meta"), dict):
        mirror_meta = out["mirror_meta"]
        signal["mirror_meta"] = {
            "backend": mirror_meta.get("backend"),
            "model": _sanitize_artifact_text(mirror_meta.get("model", ""), limit=128),
            "latency_ms": mirror_meta.get("latency_ms"),
            "prompt_mode": mirror_meta.get("prompt_mode"),
        }

    return signal


def _result_row(
    *,
    i: int,
    text: str,
    out: dict | None = None,
    problems: list[str] | None = None,
    exception: Exception | None = None,
    runtime_context: dict[str, Any],
    backend_error_limit: int = 1024,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "i": i,
        "len": len(text),
        "runtime_context": runtime_context,
        "testcase_excerpt": _sanitize_artifact_text(text, limit=_MAX_ARTIFACT_TEXT),
        "testcase_hash": _stable_digest(text),
    }

    if out is not None:
        row.update(_output_signal(out))

    normalized_problems = list(problems or [])
    if exception is not None:
        row["pass"] = False
        row["exception_type"] = type(exception).__name__
        row["exception_detail"] = _artifact_exception_detail(exception, limit=backend_error_limit)
        row["testcase_text"] = _sanitize_artifact_text(text, limit=max(_MAX_ARTIFACT_TEXT, len(text)))
        if not normalized_problems:
            normalized_problems = [_artifact_exception_problem(i, exception, limit=backend_error_limit)]
    else:
        row["pass"] = not normalized_problems
        if normalized_problems:
            row["testcase_text"] = _sanitize_artifact_text(text, limit=max(_MAX_ARTIFACT_TEXT, len(text)))

    if normalized_problems:
        row["problems"] = list(normalized_problems)

    return row


def _builtin_fuzz(
    *,
    seed: int,
    cases: int,
    max_len: int,
    runtime_context: dict[str, Any],
    max_stored: int = MAX_STORED_RESULTS,
    backend_error_limit: int = 1024,
) -> tuple[list[dict], list[str], int, int]:
    r = random.Random(seed)
    results: list[dict] = []
    problems: list[str] = []
    dropped = 0
    max_case_len_seen = 0
    for i in range(cases):
        text = _gen_case(r, max_len)
        max_case_len_seen = max(max_case_len_seen, len(text))
        try:
            out = route_turn(text, seed=seed, turn_index=i)
            ps = _check_shape(out)
            row = _result_row(
                i=i,
                text=text,
                out=out,
                problems=ps,
                runtime_context=runtime_context,
                backend_error_limit=backend_error_limit,
            )
            if len(results) < max_stored:
                results.append(row)
            else:
                dropped += 1
            if ps:
                problems.append(f"case {i}: " + "; ".join(ps))
        except Exception as e:
            row = _result_row(
                i=i,
                text=text,
                exception=e,
                runtime_context=runtime_context,
                backend_error_limit=backend_error_limit,
            )
            if len(results) < max_stored:
                results.append(row)
            else:
                dropped += 1
            problems.append(_artifact_exception_problem(i, e, limit=backend_error_limit))
    return results, problems, dropped, max_case_len_seen


def main() -> int:
    ap = argparse.ArgumentParser(prog="property_turn_fuzzer")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--cases", type=int, default=200)
    ap.add_argument("--max-len", type=int, default=400)
    ap.add_argument("--hypothesis", action="store_true", help="Use Hypothesis if installed")
    args = ap.parse_args()

    if int(args.cases) <= 0:
        print("INCOMPLETE: --cases must be >= 1")
        return 2
    if int(args.cases) > MAX_CASES_HARD:
        print(f"INCOMPLETE: --cases exceeds hard cap ({args.cases} > {MAX_CASES_HARD})")
        return 2
    if int(args.max_len) < 1:
        print("INCOMPLETE: --max-len must be >= 1")
        return 2
    if int(args.max_len) > MAX_LEN_HARD:
        print(f"INCOMPLETE: --max-len exceeds hard cap ({args.max_len} > {MAX_LEN_HARD})")
        return 2

    override_error = invalid_runs_override_reason()
    if override_error:
        print(f"INCOMPLETE: {override_error}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    mode = "builtin"
    results: list[dict] = []
    problems: list[str] = []
    dropped_results = 0
    cases_executed = 0
    max_len_requested = int(args.max_len)
    max_len_effective = int(args.max_len)
    max_case_len_seen = 0
    runtime_context = _runtime_context()

    if args.hypothesis:
        try:
            from hypothesis import given, settings
            from hypothesis import strategies as st
        except Exception:
            max_len_effective = min(200, int(args.max_len))
            report = _build_report(
                run_id=run_id,
                issue=args.issue,
                seed=args.seed,
                overall="INCOMPLETE",
                mode="hypothesis",
                details="hypothesis not installed",
                runtime_context=runtime_context,
                cases_executed=0,
                max_len_requested=max_len_requested,
                max_len_effective=max_len_effective,
                max_case_len_seen=0,
                results=[],
                results_dropped=0,
                problems=[],
                problems_dropped=0,
            )
            write_json((run_dir / "property_fuzz_report.json"), report)
            _write_bundle(
                run_dir,
                run_id=run_id,
                issue=args.issue,
                seed=args.seed,
                overall="INCOMPLETE",
                mode="hypothesis",
                cases=0,
                problems=0,
                results_dropped=0,
                problems_dropped=0,
                max_len_requested=max_len_requested,
                max_len_effective=max_len_effective,
                max_case_len_seen=0,
                runtime_context=runtime_context,
            )
            print(f"INCOMPLETE: wrote outputs to {run_dir}")
            return 2

        mode = "hypothesis"
        seen: dict[str, dict] = {}
        safe_cases = min(200, int(args.cases))
        safe_max_len = min(200, int(args.max_len))
        max_len_effective = safe_max_len
        hypothesis_counter = {"value": 0}
        try:
            @settings(max_examples=safe_cases, deadline=None)
            @given(st.text(min_size=0, max_size=safe_max_len))
            def _prop(s: str):
                idx = hypothesis_counter["value"]
                hypothesis_counter["value"] += 1
                key = str(len(s)) + ":" + _stable_digest(s)
                try:
                    out = route_turn(s, seed=args.seed)
                    ps = _check_shape(out)
                    row = _result_row(
                        i=idx,
                        text=s,
                        out=out,
                        problems=ps,
                        runtime_context=runtime_context,
                    )
                    seen[key] = row
                    if ps:
                        raise AssertionError("; ".join(ps))
                except Exception as e:
                    row = _result_row(
                        i=idx,
                        text=s,
                        exception=e,
                        runtime_context=runtime_context,
                    )
                    seen[key] = row
                    raise

            _prop()
        except Exception as e:
            problems.append(_artifact_exception_summary("hypothesis_exception", e, limit=1024))

        for _, row in list(seen.items())[: int(args.cases)]:
            results.append(row)
        cases_executed = len(seen)
        max_case_len_seen = max((int(row.get("len", 0)) for row in seen.values()), default=0)

    else:
        results, problems, dropped_results, max_case_len_seen = _builtin_fuzz(
            seed=args.seed,
            cases=int(args.cases),
            max_len=int(args.max_len),
            runtime_context=runtime_context,
            max_stored=MAX_STORED_RESULTS,
            backend_error_limit=1024,
        )
        cases_executed = int(args.cases)
    if mode == "hypothesis" and len(results) > MAX_STORED_RESULTS:
        dropped_results = len(results) - MAX_STORED_RESULTS
        results = results[:MAX_STORED_RESULTS]

    overall = "PASS" if not problems else "FAIL"
    problems_dropped = max(0, len(problems) - _MAX_REPORT_PROBLEMS)
    report = _build_report(
        run_id=run_id,
        issue=args.issue,
        seed=args.seed,
        overall=overall,
        mode=mode,
        runtime_context=runtime_context,
        cases_executed=cases_executed,
        max_len_requested=max_len_requested,
        max_len_effective=max_len_effective,
        max_case_len_seen=max_case_len_seen,
        results=results,
        results_dropped=dropped_results,
        problems=problems[:_MAX_REPORT_PROBLEMS],
        problems_dropped=problems_dropped,
    )
    write_json((run_dir / "property_fuzz_report.json"), report)
    _write_bundle(
        run_dir,
        run_id=run_id,
        issue=args.issue,
        seed=args.seed,
        overall=overall,
        mode=mode,
        cases=cases_executed,
        problems=len(problems),
        results_dropped=dropped_results,
        problems_dropped=problems_dropped,
        max_len_requested=max_len_requested,
        max_len_effective=max_len_effective,
        max_case_len_seen=max_case_len_seen,
        runtime_context=runtime_context,
    )
    print(f"{overall}: wrote outputs to {run_dir}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
