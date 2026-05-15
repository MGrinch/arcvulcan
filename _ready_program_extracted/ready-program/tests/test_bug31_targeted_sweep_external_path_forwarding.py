from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import targeted_sweep as sweep  # noqa: E402


def test_with_allow_external_path_detects_supported_tool_from_source(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tools_dir = repo_root / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "dynamic_tool.py").write_text(
        "import argparse\n"
        "ap = argparse.ArgumentParser()\n"
        "ap.add_argument('--allow-external-path', action='store_true')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sweep, "_REPO_ROOT", repo_root)
    sweep._tool_supports_allow_external_path.cache_clear()

    cmd = [sys.executable, "tools/dynamic_tool.py", str(tmp_path / "external-input")]
    forwarded = sweep._with_allow_external_path(cmd, str(tmp_path / "external-input"))

    assert forwarded[-1] == "--allow-external-path"


def test_targeted_sweep_forwards_allow_external_path_for_external_child_runs(monkeypatch, tmp_path: Path) -> None:
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

    monkeypatch.setattr(sweep, "_allocate_sweep_run_dir", fake_allocate_run_dir)
    monkeypatch.setattr(sweep, "_run_id", lambda **kwargs: "targeted_sweep_bug31")
    monkeypatch.setattr(sweep, "_step", fake_step)
    monkeypatch.setattr(sys, "argv", ["targeted_sweep.py", "--issue", "ISSUE-20260319-031"])

    rc = sweep.main()
    assert rc == 0

    for step_name in ("repro_replay_diff", "protocol_drift_radar", "mirror_calibration_bench"):
        cmd = next(cmd for name, cmd in captured if name == step_name)
        assert "--allow-external-path" in cmd
