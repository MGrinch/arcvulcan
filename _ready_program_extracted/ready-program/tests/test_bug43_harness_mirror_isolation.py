from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_TURN = REPO_ROOT / "tools" / "harness_turn.py"
HARNESS_SESSION = REPO_ROOT / "tools" / "harness_session.py"


def _run(cmd: list[str], *, tmp_path: Path, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DAEDALUS_RUNS_DIR"] = str(tmp_path / "runs")
    env.update(env_overrides)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_harness_turn_uses_real_config_override_instead_of_dead_gwen_flag(tmp_path: Path) -> None:
    proc = _run(
        [
            sys.executable,
            str(HARNESS_TURN),
            "--issue",
            "ISSUE-20260314-043",
        ],
        tmp_path=tmp_path,
        env_overrides={
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_MIRROR_BACKEND": "fault",
            "DAEDALUS_FAULT_MODE": "exception",
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    match = re.search(r"wrote outputs to (.+)$", proc.stdout.strip())
    assert match, proc.stdout + proc.stderr
    report_path = Path(match.group(1).strip()) / "turn_report.json"
    doc = json.loads(report_path.read_text(encoding="utf-8"))
    turn = doc["payload"]["turn_result"]

    assert turn["config"]["enable_mirror"] is False
    assert turn.get("mirror_prediction") is None
    assert turn.get("mirror_meta") is None
    assert "mirror_backend_error" not in str(turn.get("backend_error") or "")


def test_harness_session_requires_explicit_cli_opt_in_for_mirror(tmp_path: Path) -> None:
    env = {
        "DAEDALUS_ENABLE_MIRROR": "1",
        "DAEDALUS_MIRROR_BACKEND": "fault",
        "DAEDALUS_FAULT_MODE": "exception",
    }

    default_run_id = "bug43-session-default"
    proc_default = _run(
        [
            sys.executable,
            str(HARNESS_SESSION),
            "--issue",
            "ISSUE-20260314-043",
            "--max-turns",
            "1",
            "--run-id",
            default_run_id,
        ],
        tmp_path=tmp_path / "default",
        env_overrides=env,
    )
    assert proc_default.returncode == 0, proc_default.stdout + proc_default.stderr

    default_doc = json.loads(((tmp_path / "default" / "runs" / default_run_id / "session_report.json").read_text(encoding="utf-8")))
    default_run = json.loads(((tmp_path / "default" / "runs" / default_run_id / "run.json").read_text(encoding="utf-8")))
    default_turn = default_doc["payload"]["session_report"]["turns"][0]

    assert default_run["enable_mirror"] is False
    assert default_turn["mirror"]["answer"] is None
    assert default_turn["mirror"]["meta"] is None

    opt_in_run_id = "bug43-session-opt-in"
    proc_opt_in = _run(
        [
            sys.executable,
            str(HARNESS_SESSION),
            "--issue",
            "ISSUE-20260314-043",
            "--max-turns",
            "1",
            "--enable-mirror",
            "--run-id",
            opt_in_run_id,
        ],
        tmp_path=tmp_path / "optin",
        env_overrides=env,
    )
    assert proc_opt_in.returncode == 0, proc_opt_in.stdout + proc_opt_in.stderr

    opt_in_doc = json.loads(((tmp_path / "optin" / "runs" / opt_in_run_id / "session_report.json").read_text(encoding="utf-8")))
    opt_in_run = json.loads(((tmp_path / "optin" / "runs" / opt_in_run_id / "run.json").read_text(encoding="utf-8")))
    opt_in_turn = opt_in_doc["payload"]["session_report"]["turns"][0]

    assert opt_in_run["enable_mirror"] is True
    assert isinstance(opt_in_turn["mirror"]["meta"], dict)
    assert opt_in_turn["mirror"]["meta"].get("backend") == "mirror_stub"
    assert isinstance(opt_in_turn["mirror"]["answer"], str) and opt_in_turn["mirror"]["answer"].strip()
