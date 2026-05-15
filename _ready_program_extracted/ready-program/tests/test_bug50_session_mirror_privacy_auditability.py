from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS_SESSION = ROOT / "tools" / "harness_session.py"
SEED_SWEEP = ROOT / "tools" / "seed_sweep.py"
ISSUE = "ISSUE-20260321-050"


def _run_tool(cmd: list[str], *, runs_dir: Path, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DAEDALUS_RUNS_DIR"] = str(runs_dir)
    env.update(env_overrides)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _extract_run_dir(stdout: str) -> Path:
    match = re.search(r"wrote outputs to (.+)$", stdout.strip())
    assert match, stdout
    return Path(match.group(1).strip())


def test_harness_session_records_effective_mirror_privacy_state_in_artifacts(tmp_path: Path) -> None:
    proc = _run_tool(
        [
            sys.executable,
            str(HARNESS_SESSION),
            "--issue",
            ISSUE,
            "--max-turns",
            "1",
            "--run-id",
            "bug50-session-audit",
        ],
        runs_dir=tmp_path / "runs",
        env_overrides={
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_MIRROR_SEND_USER_CONTENT": "1",
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dir = _extract_run_dir(proc.stdout)
    run_doc = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    session_doc = json.loads((run_dir / "session_report.json").read_text(encoding="utf-8"))
    turn = session_doc["payload"]["session_report"]["turns"][0]

    assert run_doc["enable_mirror"] is True
    assert run_doc["mirror_send_user_content"] is True
    assert run_doc["mirror_prompt_mode"] == "sanitized"
    assert turn["mirror"]["meta"]["prompt_mode"] == "sanitized"


def test_harness_session_default_run_id_changes_when_effective_mirror_privacy_mode_changes(tmp_path: Path) -> None:
    redacted = _run_tool(
        [sys.executable, str(HARNESS_SESSION), "--issue", ISSUE, "--max-turns", "1"],
        runs_dir=tmp_path / "redacted" / "runs",
        env_overrides={"DAEDALUS_ENABLE_MIRROR": "1"},
    )
    assert redacted.returncode == 0, redacted.stdout + redacted.stderr

    sanitized = _run_tool(
        [sys.executable, str(HARNESS_SESSION), "--issue", ISSUE, "--max-turns", "1"],
        runs_dir=tmp_path / "sanitized" / "runs",
        env_overrides={
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_MIRROR_SEND_USER_CONTENT": "1",
        },
    )
    assert sanitized.returncode == 0, sanitized.stdout + sanitized.stderr

    redacted_dir = _extract_run_dir(redacted.stdout)
    sanitized_dir = _extract_run_dir(sanitized.stdout)

    assert redacted_dir.name != sanitized_dir.name

    redacted_run = json.loads((redacted_dir / "run.json").read_text(encoding="utf-8"))
    sanitized_run = json.loads((sanitized_dir / "run.json").read_text(encoding="utf-8"))
    assert redacted_run["mirror_prompt_mode"] == "redacted"
    assert sanitized_run["mirror_prompt_mode"] == "sanitized"


def test_seed_sweep_reports_disabled_effective_mirror_mode_when_mirror_is_off(tmp_path: Path) -> None:
    proc = _run_tool(
        [
            sys.executable,
            str(SEED_SWEEP),
            "--issue",
            ISSUE,
            "--seed-start",
            "1",
            "--seed-end",
            "2",
        ],
        runs_dir=tmp_path / "runs",
        env_overrides={"DAEDALUS_MIRROR_SEND_USER_CONTENT": "1"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((run_dir / "seed_sweep_report.json").read_text(encoding="utf-8"))
    run_doc = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    assert report["mirror_send_user_content"] is True
    assert report["mirror_prompt_mode"] == "disabled"
    assert run_doc["mirror_send_user_content"] is True
    assert run_doc["mirror_prompt_mode"] == "disabled"
    assert {sample["mirror_prompt_mode"] for sample in report["samples"]} == {"disabled"}
