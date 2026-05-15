from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tools" / "harness_session.py"
ISSUE = "ISSUE-20260319-033"


def test_harness_session_exports_env_selected_protocol_and_grounding_paths(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DAEDALUS_RUNS_DIR"] = str(runs_dir)
    env["DAEDALUS_PROTOCOL_PATH"] = "STABLE/WITNESS_PROTOCOL_v2.1.md"
    env["DAEDALUS_GROUNDING_MODE"] = "local"
    env["DAEDALUS_GROUNDING_DIR"] = "documentation/protocols"

    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "--issue",
            ISSUE,
            "--max-turns",
            "1",
            "--run-id",
            "bug33-env-paths",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dir = runs_dir / "bug33-env-paths"
    session_doc = json.loads((run_dir / "session_report.json").read_text(encoding="utf-8"))
    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    summary_md = (run_dir / "session_summary.md").read_text(encoding="utf-8")

    prompt_meta = session_doc["payload"]["session_report"]["turns"][0]["teach"]["prompt_meta"]
    assert prompt_meta["protocol_path"] == "STABLE/WITNESS_PROTOCOL_v2.1.md"
    assert prompt_meta["grounding"]["grounding_dir"] == "<abs>/protocols"

    assert run_meta["protocol_path"] == "STABLE/WITNESS_PROTOCOL_v2.1.md"
    assert run_meta["grounding_mode"] == "local"
    assert run_meta["grounding_dir"] == "documentation/protocols"
    assert run_meta["protocol_reground_every"] == 5

    assert "- protocol_path: `STABLE/WITNESS_PROTOCOL_v2.1.md`" in summary_md
    assert "- grounding_mode: `local`" in summary_md
    assert "- grounding_dir: `documentation/protocols`" in summary_md
