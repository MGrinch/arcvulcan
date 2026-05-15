from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.session_loop import run_session

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "harness_session.py"
ISSUE = "ISSUE-20260315-084"


def test_run_session_exports_close_gate_and_telemetry():
    answers = iter([
        ("fit.", {"typing_ms": 16000, "source": "test"}),
    ])

    report, _ = run_session(
        session_id="session-bug-84",
        cfg=XYZGLConfig(),
        seed=1337,
        max_turns=1,
        graph=default_graph(),
        input_provider=lambda prompt: next(answers),
    )

    exported = report.to_json()
    turn = exported["turns"][0]
    assert turn["telemetry"]["typing_ms"] == 16000
    assert turn["telemetry"]["source"] == "test"
    assert turn["eval"]["inferred_user_state"] == "frustrated"
    assert turn["close_gate"]["required_keywords"]
    assert turn["close_gate"]["matched_keywords"] == ["fit"]
    assert "gap" in turn["close_gate"]["missing_keywords"]
    assert turn["close_gate"]["satisfied"] is False


def test_harness_session_default_simulator_surfaces_auditable_state_transitions(tmp_path):
    runs_dir = tmp_path / "runs"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DAEDALUS_RUNS_DIR"] = str(runs_dir)

    proc = subprocess.run(
        [sys.executable, str(TOOL), "--issue", ISSUE, "--max-turns", "2"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    reports = list(runs_dir.rglob("session_report.json"))
    assert len(reports) == 1
    doc = json.loads(reports[0].read_text(encoding="utf-8"))
    session_report = doc["payload"]["session_report"]
    assert len(session_report["turns"]) == 2

    first, second = session_report["turns"]
    assert first["telemetry"]["typing_ms"] == 16000
    assert first["telemetry"]["simulated_mode"] == "incomplete_short"
    assert first["eval"]["inferred_user_state"] == "frustrated"
    assert first["close_gate"]["satisfied"] is False
    assert first["close_gate"]["missing_keywords"]

    assert second["telemetry"]["typing_ms"] >= 3200
    assert second["telemetry"]["simulated_mode"] == "complete_contextual"
    assert second["eval"]["inferred_user_state"] == "flow"
    assert second["close_gate"]["satisfied"] is True
    assert not second["close_gate"]["missing_keywords"]
