from __future__ import annotations

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

import harness_lattice

ISSUE_ID = "ISSUE-20260320-096"


def _fake_run_dir(tmp_path: Path):
    run_dir = tmp_path / "run"

    def allocate(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    return run_dir, allocate


def _load_lattice_report(run_dir: Path) -> dict:
    event = json.loads((run_dir / "lattice_report.json").read_text(encoding="utf-8"))
    return event["payload"]["lattice_report"]


def _base_result(text: str, reply: str) -> dict:
    return {
        "reply": reply,
        "config": {"max_chars_out": 800},
        "backend": "stub",
        "input": text,
    }


def test_harness_lattice_fails_when_all_cases_collapse_to_same_meaning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, allocate = _fake_run_dir(tmp_path)
    monkeypatch.setattr(harness_lattice, "allocate_run_dir", allocate)
    monkeypatch.setattr(harness_lattice, "_run_id", lambda: "bug96-flat")
    monkeypatch.setattr(
        harness_lattice,
        "route_turn",
        lambda text, seed=None: _base_result(text, "Safety first: Use the same generic advice every time."),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_lattice.py",
            "--issue",
            ISSUE_ID,
            "--seeds",
            "1",
            "--processes",
            "SMAW,GMAW",
            "--thicknesses",
            "3mm",
            "--defects",
            "porosity",
        ],
    )

    exit_code = harness_lattice.main()

    assert exit_code == 1
    report = _load_lattice_report(run_dir)
    semantic = report["summary"]["semantic_movement"]
    assert report["summary"]["suite_ok"] is False
    assert report["summary"]["suite_failures"] == ["no_meaningful_semantic_movement"]
    assert semantic["meaningful_movement_detected"] is False
    assert semantic["dimensions"]["process"]["groups_without_meaningful_change"] == 1


def test_harness_lattice_ignores_pure_dimension_echo_without_meaningful_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, allocate = _fake_run_dir(tmp_path)
    monkeypatch.setattr(harness_lattice, "allocate_run_dir", allocate)
    monkeypatch.setattr(harness_lattice, "_run_id", lambda: "bug96-echo")

    def mechanical_echo(text: str, seed=None) -> dict:
        process = "SMAW" if "Process: SMAW" in text else "GMAW"
        return _base_result(text, f"Safety first: Process {process} selected for this case.")

    monkeypatch.setattr(harness_lattice, "route_turn", mechanical_echo)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_lattice.py",
            "--issue",
            ISSUE_ID,
            "--seeds",
            "1",
            "--processes",
            "SMAW,GMAW",
            "--thicknesses",
            "3mm",
            "--defects",
            "porosity",
        ],
    )

    exit_code = harness_lattice.main()

    assert exit_code == 1
    report = _load_lattice_report(run_dir)
    semantic = report["summary"]["semantic_movement"]
    assert report["summary"]["suite_failures"] == ["no_meaningful_semantic_movement"]
    assert semantic["meaningful_movement_detected"] is False
    assert semantic["semantic_reply_variants"] == 1


def test_harness_lattice_passes_when_a_dimension_changes_reply_meaningfully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, allocate = _fake_run_dir(tmp_path)
    monkeypatch.setattr(harness_lattice, "allocate_run_dir", allocate)
    monkeypatch.setattr(harness_lattice, "_run_id", lambda: "bug96-delta")

    def process_specific_reply(text: str, seed=None) -> dict:
        if "Process: SMAW" in text:
            reply = "Safety first: Tighten rod angle and slag control so the SMAW root stays fused and clean."
        else:
            reply = "Safety first: Check gas coverage and wire feed stability so the GMAW transfer stays smooth."
        return _base_result(text, reply)

    monkeypatch.setattr(harness_lattice, "route_turn", process_specific_reply)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_lattice.py",
            "--issue",
            ISSUE_ID,
            "--seeds",
            "1",
            "--processes",
            "SMAW,GMAW",
            "--thicknesses",
            "3mm",
            "--defects",
            "porosity",
        ],
    )

    exit_code = harness_lattice.main()

    assert exit_code == 0
    report = _load_lattice_report(run_dir)
    semantic = report["summary"]["semantic_movement"]
    assert report["summary"]["suite_ok"] is True
    assert report["summary"]["suite_failures"] == []
    assert semantic["meaningful_movement_detected"] is True
    assert "process" in semantic["changed_dimensions"]
    assert semantic["dimensions"]["process"]["groups_with_meaningful_change"] == 1
