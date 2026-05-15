from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import targeted_sweep  # noqa: E402


def _run_and_get_dir(cmd: list[str], env: dict[str, str]) -> Path:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)
    combined = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln.strip() for ln in combined.splitlines() if "wrote outputs to " in ln]
    assert lines, combined
    run_dir = Path(lines[-1].split("wrote outputs to ", 1)[1].strip())
    assert run_dir.is_dir(), run_dir
    return run_dir


def test_stage_timing_reports_logical_determinism_even_with_unique_run_dir(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            "tools/stage_timing_profiler.py",
            "--issue",
            "ISSUE-20260319-127",
            "--seed",
            "127",
        ],
        env,
    )

    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_meta["deterministic"] is True
    assert run_meta["artifact_identity_stable"] is False
    assert run_meta["artifact_content_stable"] is True
    assert "stub-only" in run_meta["determinism_basis"]


def test_coverage_gate_explicitly_separates_nondeterministic_identity_and_content(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            "tools/coverage_gate.py",
            "--issue",
            "ISSUE-20260319-127",
            "--seed",
            "127",
            "--min-line",
            "0",
            "--min-branch",
            "0",
        ],
        env,
    )

    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_meta["deterministic"] is False
    assert run_meta["artifact_identity_stable"] is False
    assert run_meta["artifact_content_stable"] is False


def test_targeted_sweep_requires_child_identity_stability_for_parent_content_stability(tmp_path: Path) -> None:
    child_runs = tmp_path / "child_runs"
    child_runs.mkdir()

    stable = child_runs / "stable"
    stable.mkdir()
    (stable / "run.json").write_text(
        json.dumps(
            {
                "run_id": "stable",
                "deterministic": True,
                "artifact_identity_stable": True,
                "artifact_content_stable": True,
            }
        ),
        encoding="utf-8",
    )

    unstable = child_runs / "unstable"
    unstable.mkdir()
    (unstable / "run.json").write_text(
        json.dumps(
            {
                "run_id": "unstable",
                "deterministic": True,
                "artifact_identity_stable": False,
                "artifact_content_stable": True,
            }
        ),
        encoding="utf-8",
    )

    contract = targeted_sweep._collect_child_run_contract(child_runs)
    assert contract["all_deterministic"] is True
    assert contract["all_artifact_identity_stable"] is False
    assert contract["all_artifact_content_stable"] is False


def test_harness_session_marks_default_deterministic_runs_as_identity_stable(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")
    env["DAEDALUS_ENFORCE_DETERMINISM"] = "1"

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            "tools/harness_session.py",
            "--issue",
            "ISSUE-20260319-127",
            "--seed",
            "127",
            "--max-turns",
            "2",
        ],
        env,
    )

    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_meta["deterministic"] is True
    assert run_meta["artifact_identity_stable"] is True
    assert run_meta["artifact_content_stable"] is True


def test_atheris_router_describes_fallback_identity_stability_contract() -> None:
    import tools.atheris_fuzz_router as atheris_fuzz_router

    fallback_meta = atheris_fuzz_router._run_meta(
        run_id="fallback-run",
        issue="ISSUE-20260319-127",
        seed=127,
        engine="fallback",
    )
    assert fallback_meta["deterministic"] is True
    assert fallback_meta["artifact_identity_stable"] is False
    assert fallback_meta["artifact_content_stable"] is True

    atheris_meta = atheris_fuzz_router._run_meta(
        run_id="atheris-run",
        issue="ISSUE-20260319-127",
        seed=127,
        engine="atheris",
    )
    assert atheris_meta["deterministic"] is False
    assert atheris_meta["artifact_identity_stable"] is False
    assert atheris_meta["artifact_content_stable"] is False
