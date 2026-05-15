from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_latency_cost_budget_enforcer_ignores_ambient_backend_env(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))

    env = os.environ.copy()
    env.update(
        {
            "DAEDALUS_RUNS_DIR": str(runs_dir),
            "DAEDALUS_TUTOR_BACKEND": "gemini",
            "DAEDALUS_GEMINI_MODEL": "gemini-test-model",
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_MIRROR_BACKEND": "ollama",
            "DAEDALUS_OLLAMA_MODEL": "ollama-test-model",
            "DAEDALUS_REQUIRE_REAL_BACKENDS": "1",
        }
    )

    proc = subprocess.run(
        [
            sys.executable,
            "tools/latency_cost_budget_enforcer.py",
            "--issue",
            "ISSUE-20260319-041",
            "--seed",
            "41",
            "--cases",
            "1",
            "--p95-ms",
            "10000",
            "--max-est-tokens",
            "10000",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    report_path = sorted(runs_dir.glob("*/latency_budget_report.json"))[-1]
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["observed"]["mirror_latency_ms"] is None
    assert report["samples"], report
    assert all(sample["backend"] == "stub" for sample in report["samples"])
