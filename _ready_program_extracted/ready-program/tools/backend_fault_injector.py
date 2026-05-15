#!/usr/bin/env python3
from __future__ import annotations

"""Backend fault injector.

Deterministically runs a small scenario set against `xyzgl.router.route_turn()`.

Exit codes: 0 PASS, 1 FAIL.
"""

import argparse
import os
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from backend_validation_io import capture_callable, record_side_effect_failure, side_effect_reason
from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


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


def _capture_route_turn(*args, **kwargs):
    from xyzgl.router import route_turn

    return capture_callable(route_turn, *args, **kwargs)


def _scenario(
    name: str,
    *,
    expect_raise: bool,
    env: dict[str, str | None],
    expect_effective_backend: str | None = None,
    require_backend_error: bool = False,
    max_backend_error_len: int | None = None,
    expect_mirror_prediction: bool | None = None,
) -> dict:
    ok = True
    detail_parts: list[str] = []
    observed: dict = {}
    with _env_patch(env):
        ran_ok, out_or_exc, side_effects = _capture_route_turn("fault-inject", seed=123, turn_index=0)

    if ran_ok:
        out = out_or_exc
        backend_error = out.get("backend_error")
        observed = {
            "reply_nonempty": bool(out.get("reply")),
            "reply_len": len(out.get("reply") or ""),
            "backend_error": backend_error,
            "backend_error_present": bool(backend_error),
            "backend_error_len": len(backend_error or ""),
            "effective_backend": out.get("effective_backend"),
            "requested_backend": out.get("requested_backend"),
            "mirror_prediction_present": bool(out.get("mirror_prediction")),
            "side_effects": side_effects,
        }
        if side_effects["stdout_present"] or side_effects["stderr_present"]:
            ok = False
            detail_parts.append(side_effect_reason(side_effects, stage="route_turn"))
        if expect_raise:
            ok = False
            detail_parts.append("expected exception, got normal return")
        if not expect_raise and not observed["reply_nonempty"]:
            ok = False
            detail_parts.append("expected non-empty reply")
        if expect_effective_backend is not None and observed["effective_backend"] != expect_effective_backend:
            ok = False
            detail_parts.append(
                f"expected effective_backend={expect_effective_backend!r}, got {observed['effective_backend']!r}"
            )
        if require_backend_error and not observed["backend_error_present"]:
            ok = False
            detail_parts.append("expected backend_error on handled fallback")
        if max_backend_error_len is not None and observed["backend_error_len"] > max_backend_error_len:
            ok = False
            detail_parts.append(
                f"expected backend_error_len <= {max_backend_error_len}, got {observed['backend_error_len']}"
            )
        if expect_mirror_prediction is not None and observed["mirror_prediction_present"] != expect_mirror_prediction:
            ok = False
            detail_parts.append(
                f"expected mirror_prediction_present={expect_mirror_prediction}, got {observed['mirror_prediction_present']}"
            )
    else:
        e = out_or_exc
        observed = {"exception": f"{type(e).__name__}: {e}", "side_effects": side_effects}
        if side_effects["stdout_present"] or side_effects["stderr_present"]:
            ok = False
            detail_parts.append(side_effect_reason(side_effects, stage="route_turn"))
        if not expect_raise:
            ok = False
            detail_parts.append("unexpected exception")

    details = "; ".join(detail_parts)
    if details:
        observed["verdict_reasons"] = [part for part in detail_parts if part]
    return {
        "name": name,
        "expect_raise": expect_raise,
        "pass": ok,
        "observed": observed,
        "details": details,
    }


def _base_clear_env() -> dict[str, str | None]:
    return {
        "DAEDALUS_TUTOR_BACKEND": None,
        "DAEDALUS_MIRROR_BACKEND": None,
        "DAEDALUS_ENABLE_MIRROR": None,
        "DAEDALUS_GEMINI_API_KEY": None,
        "GOOGLE_API_KEY": None,
        "DAEDALUS_GEMINI_MODEL": None,
        "DAEDALUS_REQUIRE_REAL_BACKENDS": None,
        "DAEDALUS_FAULT_MODE": None,
        "DAEDALUS_FAULT_DELAY_MS": None,
        "DAEDALUS_EXPOSE_BACKEND_ERRORS": None,
        "DAEDALUS_MAX_CHARS_OUT": None,
    }



def _stock_scenarios() -> list[dict]:
    return [
        {
            "name": "missing_gemini_key_fallback",
            "expect_raise": False,
            "env": {"DAEDALUS_TUTOR_BACKEND": "gemini", "DAEDALUS_GEMINI_MODEL": "gemini-test-model"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
        },
        {
            "name": "missing_gemini_key_strict_raises",
            "expect_raise": True,
            "env": {
                "DAEDALUS_TUTOR_BACKEND": "gemini",
                "DAEDALUS_GEMINI_MODEL": "gemini-test-model",
                "DAEDALUS_REQUIRE_REAL_BACKENDS": "1",
            },
        },
        {
            "name": "tutor_fault_exception_fallback",
            "expect_raise": False,
            "env": {"DAEDALUS_TUTOR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "exception"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
        },
        {
            "name": "tutor_fault_timeout_fallback",
            "expect_raise": False,
            "env": {"DAEDALUS_TUTOR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "timeout"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
        },
        {
            "name": "tutor_fault_empty_fallback",
            "expect_raise": False,
            "env": {"DAEDALUS_TUTOR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "empty"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
        },
        {
            "name": "mirror_fault_exception_handled",
            "expect_raise": False,
            "env": {"DAEDALUS_ENABLE_MIRROR": "1", "DAEDALUS_MIRROR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "exception"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
            "expect_mirror_prediction": False,
        },
        {
            "name": "mirror_fault_empty_handled",
            "expect_raise": False,
            "env": {"DAEDALUS_ENABLE_MIRROR": "1", "DAEDALUS_MIRROR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "empty"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
            "expect_mirror_prediction": False,
        },
        {
            "name": "oversized_backend_error_bounded",
            "expect_raise": False,
            "env": {
                "DAEDALUS_TUTOR_BACKEND": "X" * 300,
                "DAEDALUS_EXPOSE_BACKEND_ERRORS": "1",
                "DAEDALUS_MAX_CHARS_OUT": "64",
            },
            "expect_effective_backend": "stub",
            "require_backend_error": True,
            "max_backend_error_len": 64,
        },
        {
            "name": "unknown_backend_config_error_fallback",
            "expect_raise": False,
            "env": {"DAEDALUS_TUTOR_BACKEND": "unknown_backend"},
            "expect_effective_backend": "stub",
            "require_backend_error": True,
        },
    ]



def main() -> int:
    p = argparse.ArgumentParser(prog="backend_fault_injector")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    base_clear = _base_clear_env()
    spec = _stock_scenarios()
    scenarios = [_scenario(env={**base_clear, **s.pop("env")}, **s) for s in [dict(item) for item in spec]]

    passed = sum(1 for s in scenarios if s["pass"])
    total = len(scenarios)
    ok = passed == total

    report = {
        "schema_version": "backend_fault_report@1",
        "tool": "backend_fault_injector",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "scenarios_total": total,
        "scenarios_passed": passed,
        "scenarios": scenarios,
    }
    write_json((run_dir / "backend_fault_report.json"), report)

    lines = [
        "# Backend Fault Injector Summary",
        "",
        f"- issue: `{args.issue}`",
        f"- run_id: `{run_id}`",
        f"- passed: `{passed}/{total}`",
        "",
    ]
    for s in scenarios:
        mark = "✅" if s["pass"] else "❌"
        lines.append(f"- {mark} {s['name']}: {s.get('details') or 'ok'}")
    (run_dir / "backend_fault_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": True,
        "outputs": ["backend_fault_report.json", "backend_fault_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(("PASS" if ok else "FAIL") + f": wrote outputs to {run_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
