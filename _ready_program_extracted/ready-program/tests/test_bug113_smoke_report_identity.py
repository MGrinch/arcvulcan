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


def _load_tool(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _run_validate(path: Path) -> int:
    validate = _load_tool(f"validate_{path.name}", "tools/validate_schemas.py")
    argv = sys.argv[:]
    try:
        sys.argv = ["validate_schemas.py", str(path)]
        return int(validate.main())
    finally:
        sys.argv = argv


def test_repro_smoke_tools_emit_tool_native_reports_and_validate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(REPO_ROOT)

    backend_module = _load_tool("repro_backends_smoke_bug113", "tools/repro_backends_smoke.py")
    backend_run_dir = tmp_path / "backend-run"
    monkeypatch.setattr(backend_module, "allocate_run_dir", lambda _run_id: backend_run_dir)
    monkeypatch.setattr(sys, "argv", ["repro_backends_smoke.py", "--issue", "ISSUE-20260320-113", "--seed", "113"])
    assert backend_module.main() == 0
    backend_report = json.loads((backend_run_dir / "repro_backends_smoke_report.json").read_text(encoding="utf-8"))
    assert backend_report["schema_version"] == "repro_backends_smoke_report@1"
    assert backend_report["tool"] == "repro_backends_smoke"
    backend_meta = json.loads((backend_run_dir / "run.json").read_text(encoding="utf-8"))
    assert "repro_backends_smoke_report.json" in backend_meta["outputs"]
    assert "backend_fault_report.json" not in backend_meta["outputs"]
    assert _run_validate(backend_run_dir) == 0

    grounding_module = _load_tool("repro_grounding_protocol_smoke_bug113", "tools/repro_grounding_protocol_smoke.py")
    grounding_run_dir = tmp_path / "grounding-run"
    monkeypatch.setattr(grounding_module, "allocate_run_dir", lambda _run_id: grounding_run_dir)
    monkeypatch.setattr(sys, "argv", [
        "repro_grounding_protocol_smoke.py",
        "--issue",
        "ISSUE-20260320-113",
        "--seed",
        "113",
    ])
    assert grounding_module.main() == 0
    grounding_report = json.loads((grounding_run_dir / "repro_grounding_protocol_smoke_report.json").read_text(encoding="utf-8"))
    assert grounding_report["schema_version"] == "repro_grounding_protocol_smoke_report@1"
    assert grounding_report["tool"] == "repro_grounding_protocol_smoke"
    grounding_meta = json.loads((grounding_run_dir / "run.json").read_text(encoding="utf-8"))
    assert "repro_grounding_protocol_smoke_report.json" in grounding_meta["outputs"]
    assert "ci_gate_report.json" not in grounding_meta["outputs"]
    assert _run_validate(grounding_run_dir) == 0


def test_validate_schemas_rejects_old_mislabeled_repro_backends_bundle(tmp_path: Path) -> None:
    run_dir = tmp_path / "old-backend-smoke"
    run_dir.mkdir()
    (run_dir / "backend_smoke_summary.md").write_text("# summary\n", encoding="utf-8")
    (run_dir / "backend_fault_report.json").write_text(
        json.dumps(
            {
                "schema_version": "backend_fault_report@1",
                "run_id": "old-backend-smoke",
                "issue_id": "ISSUE-20260320-113",
                "seed": 113,
                "scenarios_total": 1,
                "scenarios_passed": 1,
                "scenarios": [{"name": "legacy-smoke", "pass": True}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "old-backend-smoke",
                "issue_id": "ISSUE-20260320-113",
                "seed": 113,
                "deterministic": True,
                "outputs": ["backend_fault_report.json", "backend_smoke_summary.md", "run.json"],
                "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
            }
        ),
        encoding="utf-8",
    )
    assert _run_validate(run_dir) == 1


def test_validate_schemas_rejects_old_mislabeled_grounding_smoke_bundle(tmp_path: Path) -> None:
    run_dir = tmp_path / "old-grounding-smoke"
    run_dir.mkdir()
    (run_dir / "grounding_protocol_smoke_summary.md").write_text("# summary\n", encoding="utf-8")
    (run_dir / "ci_gate_report.json").write_text(
        json.dumps(
            {
                "schema_version": "ci_gate_report@1",
                "run_id": "old-grounding-smoke",
                "issue_id": "ISSUE-20260320-113",
                "seed": 113,
                "overall": "PASS",
                "steps": [{"name": "legacy-smoke", "exit_code": 0, "stdout_tail": "ok"}],
                "meta": {"every": 2},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "old-grounding-smoke",
                "issue_id": "ISSUE-20260320-113",
                "seed": 113,
                "deterministic": True,
                "outputs": ["ci_gate_report.json", "grounding_protocol_smoke_summary.md", "run.json"],
                "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
            }
        ),
        encoding="utf-8",
    )
    assert _run_validate(run_dir) == 1
