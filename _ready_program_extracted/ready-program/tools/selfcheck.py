#!/usr/bin/env python3
"""Quick selfcheck (network-free by default).

North Star intent:
  - keep this check *fast* and *low-dependency*
  - verify the canonical interaction surface (router) is runnable
  - assert a few core invariants that other tools rely on

Exit codes:
  0 PASS
  1 FAIL
  2 INCOMPLETE
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id
from xyzgl.config import XYZGLConfig
from xyzgl.router import route_turn
from xyzgl.welding_tutor import SAFETY_PREFIX


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def _assert_common_router_shape(out: dict, *, expected_input: str, expected_seed: int, expected_turn_index: int) -> None:
    _require(isinstance(out, dict), "router output is not a dict")
    required_keys = {
        "config",
        "input",
        "input_routed",
        "seed",
        "turn_index",
        "reply",
        "backend",
        "requested_backend",
        "effective_backend",
        "tutor_meta",
        "prompt_meta",
    }
    missing = sorted(required_keys - set(out.keys()))
    _require(not missing, f"missing output keys: {', '.join(missing)}")
    _require(out.get("input") == expected_input, f"input roundtrip mismatch ({out.get('input')!r})")
    _require(out.get("input_routed") == expected_input, f"input_routed roundtrip mismatch ({out.get('input_routed')!r})")
    _require(out.get("seed") == expected_seed, f"seed roundtrip mismatch ({out.get('seed')!r})")
    _require(out.get("turn_index") == expected_turn_index, f"turn_index mismatch ({out.get('turn_index')!r})")
    _require(isinstance(out.get("reply"), str) and bool(out.get("reply")), "empty reply")
    _require(out["reply"].startswith(SAFETY_PREFIX), "reply missing safety prefix")

    tutor_meta = out.get("tutor_meta")
    _require(isinstance(tutor_meta, dict), "tutor_meta is not a dict")
    _require(out.get("backend") == out.get("effective_backend"), "backend/effective_backend drift")
    _require(out.get("backend") == tutor_meta.get("backend"), "backend/tutor_meta.backend drift")

    prompt_meta = out.get("prompt_meta")
    _require(isinstance(prompt_meta, dict), "prompt_meta is not a dict")
    for key in ("protocol_regrounded", "protocol_path", "grounding_enabled", "grounding"):
        _require(key in prompt_meta, f"prompt_meta missing {key}")
    _require(isinstance(prompt_meta.get("grounding"), dict), "prompt_meta.grounding is not a dict")
    protocol_path = str(prompt_meta.get("protocol_path") or "")
    _require(not protocol_path.startswith("/") and ":\\" not in protocol_path, "prompt_meta.protocol_path leaked absolute path")

    config = out.get("config")
    _require(isinstance(config, dict), "config is not a dict")
    _require(config.get("tutor_backend") == "stub", f"unexpected tutor_backend ({config.get('tutor_backend')!r})")
    _require(not out.get("backend_error"), f"unexpected backend_error ({out.get('backend_error')!r})")


def _run_checks(*, seed: int) -> tuple[str, list[dict[str, object]]]:
    checks: list[dict[str, object]] = []
    try:
        baseline = route_turn("  selfcheck\n", seed=seed)
        _assert_common_router_shape(baseline, expected_input="selfcheck", expected_seed=seed, expected_turn_index=0)
        _require(baseline["prompt_meta"]["protocol_regrounded"] is True, "turn 0 should reground protocol")
        _require(baseline["prompt_meta"]["grounding_enabled"] is False, "default selfcheck should not enable grounding")
        checks.append({"name": "baseline_router_shape", "pass": True, "message": "turn 0 router invariants ok"})

        bounded_cfg = XYZGLConfig(max_chars_in=8, max_chars_out=24)
        bounded = route_turn("  abcdefghijklmnop  ", seed=seed + 1, cfg=bounded_cfg, turn_index=1)
        _assert_common_router_shape(bounded, expected_input="abcdefgh", expected_seed=seed + 1, expected_turn_index=1)
        _require(bounded["prompt_meta"]["protocol_regrounded"] is False, "turn 1 should not reground with default cadence")
        _require(len(bounded["input"]) == 8, f"input clamp mismatch ({len(bounded['input'])})")
        _require(len(bounded["reply"]) <= 24, f"reply clamp mismatch ({len(bounded['reply'])})")
        checks.append({"name": "bounded_io_contract", "pass": True, "message": "input/output bounds enforced"})
        return "PASS", checks
    except AssertionError as e:
        checks.append({"name": "router_invariants", "pass": False, "message": str(e)})
        return "FAIL", checks


def _write_bundle(*, issue_id: str, seed: int, overall: str, checks: list[dict[str, object]]) -> Path:
    run_id = make_run_id("selfcheck", issue_id, seed)
    run_dir = allocate_run_dir(run_id)
    report = {
        "schema_version": "selfcheck_report@1",
        "run_id": run_dir.name,
        "issue_id": issue_id,
        "seed": seed,
        "overall": overall,
        "checks": checks,
    }
    write_json(run_dir / "selfcheck_report.json", report)

    summary = [
        "# Selfcheck Summary",
        "",
        f"- issue: `{issue_id}`",
        f"- run_id: `{run_dir.name}`",
        f"- seed: `{seed}`",
        f"- overall: **{overall}**",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check.get("pass") else "FAIL"
        summary.append(f"- `{check.get('name')}`: **{status}** — {check.get('message')}")
    summary.append("")
    (run_dir / "selfcheck_summary.md").write_text("\n".join(summary), encoding="utf-8")
    write_json(
        run_dir / "run.json",
        {
            "run_id": run_dir.name,
            "issue_id": issue_id,
            "deterministic": True,
            "outputs": ["selfcheck_report.json", "selfcheck_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )
    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(prog="selfcheck")
    ap.add_argument("--issue", help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1, help="base seed for deterministic router checks")
    args = ap.parse_args()

    if args.issue is not None:
        err = validate_issue_id(args.issue)
        if err:
            print(f"INCOMPLETE: {err}")
            return 2

    overall, checks = _run_checks(seed=int(args.seed))
    if args.issue:
        run_dir = _write_bundle(issue_id=args.issue, seed=int(args.seed), overall=overall, checks=checks)
        print(f"{overall}: wrote outputs to {run_dir}")
        return 0 if overall == "PASS" else 1

    if overall != "PASS":
        return _fail(str(checks[-1].get("message") or "selfcheck failed"))
    print("PASS: router invariants ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
