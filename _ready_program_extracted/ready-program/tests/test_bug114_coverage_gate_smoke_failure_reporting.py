from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for entry in (REPO_ROOT, REPO_ROOT / "tools"):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

_spec = importlib.util.spec_from_file_location("coverage_gate_under_test", REPO_ROOT / "tools" / "coverage_gate.py")
assert _spec and _spec.loader
coverage_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coverage_gate)

ISSUE_ID = "ISSUE-20260319-114"


class _FakeCoverage:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def json_report(self, *, outfile: str) -> None:
        Path(outfile).write_text(
            json.dumps(
                {
                    "totals": {
                        "percent_covered": 100.0,
                        "num_statements": 10,
                        "covered_lines": 10,
                        "num_branches": 4,
                        "covered_branches": 4,
                        "missing_lines": 0,
                        "missing_branches": 0,
                    }
                }
            ),
            encoding="utf-8",
        )


def _fake_tool_module(name: str, returncode: int) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = f"/{name.replace('.', '/')}.py"

    def main() -> int:
        print(f"child-{name}: wrote outputs to /tmp/{name.rsplit('.', 1)[-1]}")
        return returncode

    module.main = main  # type: ignore[attr-defined]
    return module


@pytest.fixture()
def _stubbed_coverage_gate_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(tmp_path / "runs"))

    coverage_mod = types.ModuleType("coverage")
    coverage_mod.Coverage = _FakeCoverage  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "coverage", coverage_mod)

    router_mod = types.ModuleType("xyzgl.router")
    router_mod.route_turn = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xyzgl.router", router_mod)

    backends_smoke = _fake_tool_module("tools.repro_backends_smoke", 1)
    grounding_smoke = _fake_tool_module("tools.repro_grounding_protocol_smoke", 0)
    session_smoke = _fake_tool_module("tools.repro_session_smoke", 0)
    monkeypatch.setitem(sys.modules, "tools.repro_backends_smoke", backends_smoke)
    monkeypatch.setitem(sys.modules, "tools.repro_grounding_protocol_smoke", grounding_smoke)
    monkeypatch.setitem(sys.modules, "tools.repro_session_smoke", session_smoke)

    config_mod = types.ModuleType("xyzgl.config")

    class XYZGLConfig:
        pass

    config_mod.XYZGLConfig = XYZGLConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xyzgl.config", config_mod)

    graph_mod = types.ModuleType("xyzgl.knowledge.graph")
    graph_mod.default_graph = lambda: {}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xyzgl.knowledge.graph", graph_mod)

    session_loop_mod = types.ModuleType("xyzgl.orchestrator.session_loop")
    session_loop_mod.run_session = lambda **kwargs: (None, None)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xyzgl.orchestrator.session_loop", session_loop_mod)


def test_coverage_gate_reports_smoke_only_failures_without_threshold_mislabel_or_child_stdout_bleed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    _stubbed_coverage_gate_runtime: None,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "coverage_gate.py",
            "--issue",
            ISSUE_ID,
            "--seed",
            "114",
            "--min-line",
            "0",
            "--min-branch",
            "0",
        ],
    )

    rc = coverage_gate.main()

    assert rc == 1
    captured = capsys.readouterr()
    stdout_lines = [line.strip() for line in captured.out.splitlines() if line.strip()]
    assert len(stdout_lines) == 1, captured.out
    assert stdout_lines[0].startswith("FAIL_SMOKE: wrote outputs to ")
    assert "child-tools.repro_backends_smoke" not in captured.out
    assert captured.err == ""

    run_dir = Path(stdout_lines[0].split("wrote outputs to ", 1)[1].strip())
    report = json.loads((run_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "FAIL_SMOKE"
    assert report["failure_reasons"] == ["smoke_regression"]
    assert report["smoke_failures"] == ["repro_backends_smoke"]

    summary = (run_dir / "coverage_summary.md").read_text(encoding="utf-8")
    assert "FAIL: smoke regressions; smoke_failures=repro_backends_smoke" in summary
    assert "thresholds not met" not in summary
