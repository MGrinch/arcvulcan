from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import ci_gate  # noqa: E402
import targeted_sweep  # noqa: E402


def _extract_run_dir(stdout: str) -> Path:
    lines = [ln.strip() for ln in (stdout or "").splitlines() if "wrote " in ln]
    assert lines, stdout
    line = lines[-1]
    if "wrote outputs to " in line:
        return Path(line.rsplit("wrote outputs to ", 1)[1].rstrip(")").strip())
    if "(wrote " in line:
        return Path(line.rsplit("(wrote ", 1)[1].rstrip(")").strip())
    raise AssertionError(stdout)


def test_mirror_calibration_default_threshold_is_meaningful(tmp_path: Path) -> None:
    session_report = tmp_path / "session_report.json"
    session_report.write_text(
        json.dumps(
            {
                "turns": [
                    {
                        "turn_index": 1,
                        "node_id": "n1",
                        "mirror": {"answer": "alpha beta gamma delta"},
                        "eval": {"user_answer": "zzzz yyyy xxxx qqqq"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "mirror_calibration_bench.py"),
            str(session_report),
            "--issue",
            "ISSUE-20260318-131",
            "--allow-external-path",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "mirror_calibration_report.json").read_text(encoding="utf-8"))
    assert report["min_avg"] == 0.35
    assert report["avg_seqmatch"] < report["min_avg"]


def test_ci_gate_passes_nontrivial_mirror_threshold(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "ci_gate_run"
    captured: list[tuple[str, list[str]]] = []

    def fake_allocate_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def fake_run_step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path):
        captured.append((name, list(cmd)))
        if name == "harness_session":
            session_dir = Path(env["DAEDALUS_RUNS_DIR"]) / "session_run"
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "run.json").write_text("{}", encoding="utf-8")
            return 0, f"PASS: wrote outputs to {session_dir}", f"PASS: wrote outputs to {session_dir}"
        return 0, "PASS", "PASS"

    monkeypatch.setattr(ci_gate, "allocate_run_dir", fake_allocate_run_dir)
    monkeypatch.setattr(ci_gate, "_run_id", lambda: "ci_gate_bug131")
    monkeypatch.setattr(ci_gate, "_run_step", fake_run_step)
    monkeypatch.setattr(sys, "argv", ["ci_gate.py", "--issue", "ISSUE-20260318-131"])

    rc = ci_gate.main()
    assert rc == 0

    mirror_cmd = next(cmd for name, cmd in captured if name == "mirror_calibration_bench")
    assert "--min-avg" in mirror_cmd
    assert mirror_cmd[mirror_cmd.index("--min-avg") + 1] == "0.35"


def test_targeted_sweep_keeps_explicit_mirror_threshold(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "targeted_sweep_run"
    captured: list[tuple[str, list[str]]] = []

    def fake_allocate_run_dir(run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _write_child_run(child_root: Path, name: str, seed: int) -> Path:
        child_dir = child_root / name
        child_dir.mkdir(parents=True, exist_ok=True)
        (child_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": name,
                    "seed": seed,
                    "deterministic": True,
                    "artifact_identity_stable": True,
                    "artifact_content_stable": True,
                    "outputs": ["session_report.json", "knowledge_graph.json", "run.json"],
                }
            ),
            encoding="utf-8",
        )
        (child_dir / "session_report.json").write_text("{}", encoding="utf-8")
        (child_dir / "knowledge_graph.json").write_text("{}", encoding="utf-8")
        return child_dir

    def fake_step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path):
        captured.append((name, list(cmd)))
        child_root = Path(env["DAEDALUS_RUNS_DIR"])
        if name == "harness_session_mirror":
            child_dir = _write_child_run(child_root, "session_one", 1337)
            return 0, f"PASS: wrote outputs to {child_dir}", f"PASS: wrote outputs to {child_dir}", None
        if name == "harness_session_diff":
            child_dir = _write_child_run(child_root, "session_two", 1338)
            return 0, f"PASS: wrote outputs to {child_dir}", f"PASS: wrote outputs to {child_dir}", None
        return 0, "PASS", "PASS", None

    monkeypatch.setattr(targeted_sweep, "_allocate_sweep_run_dir", fake_allocate_run_dir)
    monkeypatch.setattr(targeted_sweep, "_run_id", lambda **kwargs: "targeted_sweep_bug131")
    monkeypatch.setattr(targeted_sweep, "_step", fake_step)
    monkeypatch.setattr(sys, "argv", ["targeted_sweep.py", "--issue", "ISSUE-20260318-131"])

    rc = targeted_sweep.main()
    assert rc == 0

    mirror_cmd = next(cmd for name, cmd in captured if name == "mirror_calibration_bench")
    assert "--min-avg" in mirror_cmd
    assert mirror_cmd[mirror_cmd.index("--min-avg") + 1] == "0.35"
