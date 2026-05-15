#!/usr/bin/env python3
from __future__ import annotations

"""Backend contract probe.

Checks the internal `generate()` contract across Tutor/Mirror backends.
Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

import argparse
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

from xyzgl.config import XYZGLConfig
from backend_validation_io import capture_callable, empty_side_effect_meta, record_side_effect_failure
from xyzgl.backends.registry import BackendConfigError, get_mirror_backend, get_tutor_backend


_NON_RAISING_FAULT_MODES = {"slow", "empty"}
_RAISING_FAULT_MODES = {"exception", "timeout"}


def _allowed_backend_labels(role: str, backend_name: str) -> set[str]:
    name = (backend_name or "").strip().lower()
    if role == "tutor":
        if name == "stub":
            return {"stub"}
        if name == "fault":
            return {"tutor_fault"}
        if name == "gemini":
            return {"gemini"}
    else:
        if name in {"stub", "mirror_stub"}:
            return {"mirror_stub"}
        if name == "fault":
            return {"mirror_fault"}
        if name == "ollama":
            return {"ollama"}
    return {name} if name else set()


def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"


def _fault_mode() -> str:
    return os.environ.get("DAEDALUS_FAULT_MODE", "exception").strip().lower() or "exception"


def _fault_mode_expects_raise(mode: str) -> bool:
    if mode in _RAISING_FAULT_MODES:
        return True
    if mode in _NON_RAISING_FAULT_MODES:
        return False
    return True


def _capture_call(fn, /, *args, **kwargs):
    return capture_callable(fn, *args, **kwargs)


def _fail_on_side_effects(out: dict, side_effects: dict, *, stage: str) -> bool:
    return record_side_effect_failure(out, side_effects, stage=stage)


def _probe_one(
    role: str,
    backend_name: str,
    *,
    cfg: XYZGLConfig,
    seed: int | None,
    allow_network: bool,
    expected_raise: bool = False,
) -> dict:
    """Return result dict with status PASS/FAIL/INCOMPLETE."""
    out = {"role": role, "backend": backend_name, "status": "PASS"}
    if role == "tutor":
        ok, backend_or_exc, side_effects = _capture_call(get_tutor_backend, cfg)
    else:
        ok, backend_or_exc, side_effects = _capture_call(get_mirror_backend, cfg)

    if _fail_on_side_effects(out, side_effects, stage="backend_init"):
        return out

    if not ok:
        e = backend_or_exc
        if isinstance(e, BackendConfigError):
            if allow_network:
                out["status"] = "FAIL"
                out["error"] = f"config_error: {e}"
            else:
                out["status"] = "INCOMPLETE"
                out["error"] = f"config_error: {e}"
        else:
            out["status"] = "FAIL"
            out["error"] = f"backend_init_raised: {e!r}"
        out["side_effects"] = side_effects
        return out

    backend = backend_or_exc
    prompt = "Contract probe: return a short, deterministic reply."
    if role == "mirror":
        prompt = "Mirror contract probe: reply as the learner in 1 sentence."

    # Never call real networks unless allow_network=True.
    if backend_name in {"gemini", "ollama"} and not allow_network:
        out["status"] = "INCOMPLETE"
        out["error"] = "network backend disabled (use --allow-network)"
        out["side_effects"] = empty_side_effect_meta()
        return out

    ok, res_or_exc, side_effects = _capture_call(backend.generate, prompt, seed=seed)
    if _fail_on_side_effects(out, side_effects, stage="generate"):
        return out

    if not ok:
        e = res_or_exc
        if expected_raise:
            out["status"] = "PASS"
            out["meta"] = {"expected_raise": True, "error": f"{e!r}"}
        else:
            out["status"] = "FAIL"
            out["error"] = f"generate_raised: {e!r}"
        out["side_effects"] = side_effects
        return out

    res = res_or_exc
    if expected_raise:
        out["status"] = "FAIL"
        out["error"] = "expected backend to raise, but it returned normally"
        out["side_effects"] = side_effects
        return out

    # Contract checks
    try:
        text = getattr(res, "text")
        backend = getattr(res, "backend")
        model = getattr(res, "model")
        latency_ms = getattr(res, "latency_ms")
    except Exception as e:
        out["status"] = "FAIL"
        out["error"] = f"missing_fields: {e!r}"
        out["side_effects"] = side_effects
        return out

    if not isinstance(text, str):
        out["status"] = "FAIL"
        out["error"] = f"text not str: {type(text)}"
        out["side_effects"] = side_effects
        return out
    if not text.strip():
        out["status"] = "FAIL"
        out["error"] = "text field empty or whitespace"
        out["side_effects"] = side_effects
        return out
    if not isinstance(backend, str) or not backend.strip():
        out["status"] = "FAIL"
        out["error"] = "backend field empty or not str"
        out["side_effects"] = side_effects
        return out
    allowed_backend_labels = _allowed_backend_labels(role, backend_name)
    normalized_backend = backend.strip().lower()
    if allowed_backend_labels and normalized_backend not in allowed_backend_labels:
        out["status"] = "FAIL"
        out["error"] = f"backend label mismatch: expected one of {sorted(allowed_backend_labels)!r}, got {backend!r}"
        out["side_effects"] = side_effects
        return out
    if not isinstance(model, str):
        out["status"] = "FAIL"
        out["error"] = "model field not str"
        out["side_effects"] = side_effects
        return out
    if not model.strip():
        out["status"] = "FAIL"
        out["error"] = "model field empty or whitespace"
        out["side_effects"] = side_effects
        return out
    if isinstance(latency_ms, bool) or not isinstance(latency_ms, int) or latency_ms < 0:
        out["status"] = "FAIL"
        out["error"] = f"latency_ms invalid: {latency_ms!r}"
        out["side_effects"] = side_effects
        return out

    out["meta"] = {"backend": backend, "model": model, "latency_ms": latency_ms, "text_len": len(text)}
    out["side_effects"] = side_effects
    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="backend_contract_probe")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--allow-network", action="store_true", help="Allow calling real network backends")
    p.add_argument("--include-real", action="store_true", help="Also probe gemini (tutor) and ollama (mirror)")
    p.add_argument("--include-fault", action="store_true", help="Also probe fault backend (expected to raise)")
    p.add_argument("--tutor-backends", default="stub", help="Comma-separated tutor backends")
    p.add_argument("--mirror-backends", default="stub", help="Comma-separated mirror backends")
    args = p.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    tutor_list = [s.strip() for s in args.tutor_backends.split(",") if s.strip()]
    mirror_list = [s.strip() for s in args.mirror_backends.split(",") if s.strip()]
    if args.include_real:
        if "gemini" not in tutor_list:
            tutor_list.append("gemini")
        if "ollama" not in mirror_list:
            mirror_list.append("ollama")
    fault_mode = _fault_mode()
    fault_expected_raise = _fault_mode_expects_raise(fault_mode)
    if args.include_fault:
        if "fault" not in tutor_list:
            tutor_list.append("fault")
        if "fault" not in mirror_list:
            mirror_list.append("fault")

    if not tutor_list and not mirror_list:
        print("INCOMPLETE: no backends selected; specify at least one tutor or mirror backend")
        return 2

    random.seed(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    results: list[dict] = []
    status_set: set[str] = set()

    for b in tutor_list:
        cfg = XYZGLConfig(tutor_backend=b, enable_mirror=False)
        expected_raise = fault_expected_raise if b == "fault" else False
        results.append(_probe_one("tutor", b, cfg=cfg, seed=args.seed, allow_network=bool(args.allow_network), expected_raise=expected_raise))

    for b in mirror_list:
        cfg = XYZGLConfig(mirror_backend=b, enable_mirror=True)
        expected_raise = fault_expected_raise if b == "fault" else False
        results.append(_probe_one("mirror", b, cfg=cfg, seed=args.seed, allow_network=bool(args.allow_network), expected_raise=expected_raise))

    for r in results:
        status_set.add(r.get("status") or "FAIL")

    overall = "PASS"
    if not results:
        overall = "INCOMPLETE"
    elif "FAIL" in status_set:
        overall = "FAIL"
    elif "INCOMPLETE" in status_set:
        overall = "INCOMPLETE"

    report = {
        "schema_version": "backend_contract_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "allow_network": bool(args.allow_network),
        "results": results,
        "overall": overall,
    }

    write_json((run_dir / "backend_contract_report.json"), report)

    run_meta = {
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "deterministic": not args.allow_network,
        "outputs": ["backend_contract_report.json", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }
    write_json((run_dir / "run.json"), run_meta)

    print(f"{overall}: wrote outputs to {run_dir}")
    return 1 if overall == "FAIL" else (2 if overall == "INCOMPLETE" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
