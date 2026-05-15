from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_property_turn_fuzzer_redacts_invalid_fault_mode_in_exception_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    secret_mode = "sk_live_super_secret_bad_mode"

    env = os.environ.copy()
    env.update(
        {
            "DAEDALUS_RUNS_DIR": str(runs_dir),
            "DAEDALUS_TUTOR_BACKEND": "fault",
            "DAEDALUS_REQUIRE_REAL_BACKENDS": "1",
            "DAEDALUS_EXPOSE_BACKEND_ERRORS": "0",
            "DAEDALUS_FAULT_MODE": secret_mode,
        }
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "property_turn_fuzzer.py"),
            "--issue",
            "BUG-87",
            "--cases",
            "1",
            "--max-len",
            "24",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr

    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    assert run_dirs
    report_path = run_dirs[-1] / "property_fuzz_report.json"
    report_text = report_path.read_text(encoding="utf-8")
    report = json.loads(report_text)

    assert secret_mode not in report_text
    assert "unknown fault mode" not in report_text
    assert report["runtime_context"]["fault_mode"] == "invalid_redacted"
    assert report["results"][0]["exception_detail"] == "backend_error_redacted"
    assert report["problems"][0].endswith("backend_error_redacted")
