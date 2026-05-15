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


def _run_and_get_dir(cmd: list[str], env: dict[str, str]) -> Path:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)
    combined = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln.strip() for ln in combined.splitlines() if "wrote outputs to " in ln]
    assert lines, combined
    run_dir = Path(lines[-1].split("wrote outputs to ", 1)[1].strip())
    assert run_dir.is_dir(), run_dir
    return run_dir



def _assert_declares_and_materializes_child_runs(run_dir: Path) -> None:
    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert "child_runs/" in run_meta.get("outputs", [])

    child_runs_dir = run_dir / "child_runs"
    assert child_runs_dir.is_dir(), child_runs_dir

    child_run_jsons = sorted(child_runs_dir.glob("*/run.json"))
    assert child_run_jsons, sorted(str(p.relative_to(run_dir)) for p in child_runs_dir.rglob("*"))



def test_coverage_gate_declares_child_runs_in_parent_manifest(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            "tools/coverage_gate.py",
            "--issue",
            "ISSUE-20260318-144",
            "--seed",
            "144",
            "--min-line",
            "0",
            "--min-branch",
            "0",
        ],
        env,
    )

    _assert_declares_and_materializes_child_runs(run_dir)



def test_ci_gate_declares_child_runs_in_parent_manifest(tmp_path: Path, monkeypatch) -> None:
    import tools.ci_gate as ci_gate

    run_dir = tmp_path / "runs" / "ci-parent"
    child_run_dir = run_dir / "child_runs" / "session-child"

    def fake_allocate_run_dir(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_run_step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path) -> tuple[int, str, str]:
        if name == "harness_session":
            child_run_dir.mkdir(parents=True, exist_ok=True)
            (child_run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "run_id": "session-child",
                        "issue_id": "ISSUE-20260318-144",
                        "deterministic": False,
                        "outputs": ["run.json", "session_report.json"],
                        "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
                    }
                ),
                encoding="utf-8",
            )
            (child_run_dir / "session_report.json").write_text("{}", encoding="utf-8")
            raw = f"PASS: wrote outputs to {child_run_dir}"
            return 0, raw, raw
        return 0, f"PASS: {name}", f"PASS: {name}"

    monkeypatch.setattr(ci_gate, "allocate_run_dir", fake_allocate_run_dir)
    monkeypatch.setattr(ci_gate, "_run_step", fake_run_step)
    monkeypatch.setattr(ci_gate, "_run_id", lambda: "ci-parent")

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            "ci_gate.py",
            "--issue",
            "ISSUE-20260318-144",
            "--seed",
            "144",
            "--max-turns",
            "1",
            "--step-timeout",
            "1",
        ]
        rc = ci_gate.main()
    finally:
        sys.argv = old_argv

    assert rc == 0
    _assert_declares_and_materializes_child_runs(run_dir)
