from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _load_ci_gate_module():
    spec = importlib.util.spec_from_file_location(
        "ci_gate_under_test_bug137", REPO_ROOT / "tools" / "ci_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _configure_gate(monkeypatch: pytest.MonkeyPatch, gate_module, run_dir: Path) -> None:
    monkeypatch.setattr(gate_module, "_run_id", lambda: "ci_gate_bug137")

    def _allocate(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(gate_module, "allocate_run_dir", _allocate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_gate.py",
            "--issue",
            "ISSUE-20260318-137",
            "--seed",
            "137",
            "--max-turns",
            "1",
            "--step-timeout",
            "5",
        ],
    )


def test_ci_gate_invokes_secret_scanner_with_enforcement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate_module = _load_ci_gate_module()
    run_dir = tmp_path / "runs" / "ci-gate-enforced"
    seen_steps: list[tuple[str, list[str]]] = []

    _configure_gate(monkeypatch, gate_module, run_dir)

    def _fake_run_step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path):
        seen_steps.append((name, list(cmd)))
        if name == "harness_session":
            session_dir = Path(env["DAEDALUS_RUNS_DIR"]) / "session-child"
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "run.json").write_text("{}", encoding="utf-8")
            out = f"PASS: wrote outputs to {session_dir}"
            return 0, out, out
        return 0, f"PASS: {name}", f"PASS: {name}"

    monkeypatch.setattr(gate_module, "_run_step", _fake_run_step)

    rc = gate_module.main()

    assert rc == 0
    secret_cmd = next(cmd for name, cmd in seen_steps if name == "secret_scanner")
    assert secret_cmd[:4] == [sys.executable, "tools/secret_scanner.py", "--issue", "ISSUE-20260318-137"]
    assert "--enforce" in secret_cmd

    report = json.loads((run_dir / "ci_gate_report.json").read_text(encoding="utf-8"))
    secret_step = next(step for step in report["steps"] if step["name"] == "secret_scanner")
    assert secret_step["exit_code"] == 0
    assert report["overall"] == "PASS"



def test_ci_gate_fails_closed_when_secret_scanner_hits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate_module = _load_ci_gate_module()
    run_dir = tmp_path / "runs" / "ci-gate-secret-hit"

    _configure_gate(monkeypatch, gate_module, run_dir)

    def _fake_run_step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path):
        if name == "secret_scanner":
            out = "FAIL: secret_scanner detected 1 hit"
            return 1, out, out
        if name == "harness_session":
            session_dir = Path(env["DAEDALUS_RUNS_DIR"]) / "session-child"
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "run.json").write_text("{}", encoding="utf-8")
            out = f"PASS: wrote outputs to {session_dir}"
            return 0, out, out
        return 0, f"PASS: {name}", f"PASS: {name}"

    monkeypatch.setattr(gate_module, "_run_step", _fake_run_step)

    rc = gate_module.main()

    assert rc == 1
    report = json.loads((run_dir / "ci_gate_report.json").read_text(encoding="utf-8"))
    assert report["overall"] == "FAIL"

    secret_step = next(step for step in report["steps"] if step["name"] == "secret_scanner")
    assert secret_step["exit_code"] == 1
    assert "detected 1 hit" in secret_step["stdout_tail"]
