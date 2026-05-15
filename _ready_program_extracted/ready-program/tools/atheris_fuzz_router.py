#!/usr/bin/env python3
from __future__ import annotations

"""Fuzz harness for xyzgl.router.route_turn.

- If `atheris` is installed: run a bounded coverage-guided fuzz session.
- Otherwise: run a deterministic fallback fuzzer (fixed case count).

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

import argparse, json, os, random, sys, time
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1"); sys.dont_write_bytecode = True
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path: sys.path.insert(0, str(_REPO_ROOT))

from json_canon import write_json
from run_paths import allocate_run_dir

def _run_id() -> str:
    return f"{int(time.time()*1000)}-{random.randint(1000,9999)}"

def _run_meta(*, run_id: str, issue: str, seed: int, engine: str) -> dict:
    engine_name = str(engine or "").strip().lower()
    fallback = engine_name == "fallback"
    return {
        "run_id": run_id,
        "issue_id": issue,
        "seed": seed,
        "deterministic": fallback,
        "artifact_identity_stable": False,
        "artifact_content_stable": fallback,
        "determinism_basis": (
            "fixed-seed fallback loop is logically reproducible, but the default run directory id is wall-clock/random"
            if fallback
            else "coverage-guided Atheris execution can vary across runs and the default run directory id is wall-clock/random"
        ),
        "outputs": ["atheris_fuzz_report.json", "atheris_fuzz_summary.md", "run.json"],
        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
    }


def _write_bundle(run_dir: Path, run_id: str, issue: str, seed: int, report: dict, overall: str) -> None:
    write_json((run_dir / "atheris_fuzz_report.json"), report)
    (run_dir / "atheris_fuzz_summary.md").write_text(
        "\n".join(["# Fuzz Router", "", f"- overall: **{overall}**", f"- engine: `{report.get('engine')}`", ""]),
        encoding="utf-8",
    )
    write_json((run_dir / "run.json"), _run_meta(run_id=run_id, issue=issue, seed=seed, engine=str(report.get("engine") or "")))

def main() -> int:
    p = argparse.ArgumentParser(prog="atheris_fuzz_router")
    p.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--seconds", type=int, default=10, help="used to derive deterministic case count")
    args = p.parse_args()

    if args.seconds <= 0:
        print("INCOMPLETE: --seconds must be > 0")
        return 2

    rng = random.Random(args.seed)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    report = {
        "schema_version": "atheris_fuzz_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "seed": args.seed,
        "seconds": args.seconds,
        "pass": False,
        "status": "FAIL",
        "notes": "",
    }

    from xyzgl.router import route_turn

    try:
        import atheris  # type: ignore
    except Exception as import_exc:
        report["engine"] = "fallback"
        cases = max(1, int(args.seconds)) * 200
        report["cases_planned"] = cases
        try:
            for _i in range(cases):
                n = rng.randint(0, 2048)
                b = bytes(rng.getrandbits(8) for _ in range(n))
                s = b.decode("utf-8", errors="ignore")
                _ = route_turn(s, seed=1, turn_index=0)
            report.update(
                {
                    "pass": False,
                    "status": "INCOMPLETE",
                    "notes": f"fallback fuzz ok ({cases} cases); atheris unavailable ({type(import_exc).__name__}: {import_exc})",
                }
            )
            _write_bundle(run_dir, run_id, args.issue, args.seed, report, "INCOMPLETE")
            print(f"INCOMPLETE: wrote outputs to {run_dir}")
            return 2
        except Exception as fallback_exc:
            report.update({"pass": False, "status": "FAIL", "notes": f"exception: {type(fallback_exc).__name__}: {fallback_exc}"})
            _write_bundle(run_dir, run_id, args.issue, args.seed, report, "FAIL")
            print(f"FAIL: wrote outputs to {run_dir}")
            return 1

    report["engine"] = "atheris"

    def TestOneInput(data: bytes) -> None:
        b = data[:2048]
        s = b.decode("utf-8", errors="ignore")
        _ = route_turn(s, seed=1, turn_index=0)

    old_argv = list(sys.argv)
    try:
        sys.argv = [sys.argv[0], f"-max_total_time={int(max(1, args.seconds))}"]
        atheris.Setup(sys.argv, TestOneInput)
        try:
            atheris.Fuzz()
        except SystemExit:
            pass
    except Exception as atheris_exc:
        report.update({"pass": False, "status": "FAIL", "notes": f"atheris execution failed ({type(atheris_exc).__name__}: {atheris_exc})"})
        _write_bundle(run_dir, run_id, args.issue, args.seed, report, "FAIL")
        print(f"FAIL: wrote outputs to {run_dir}")
        return 1
    finally:
        sys.argv = old_argv

    report.update({"pass": True, "status": "PASS", "notes": "completed atheris fuzz"})
    _write_bundle(run_dir, run_id, args.issue, args.seed, report, "PASS")
    print(f"PASS: wrote outputs to {run_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
