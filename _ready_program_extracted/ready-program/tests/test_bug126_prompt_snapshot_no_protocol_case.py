from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import GROUNDING_OPEN, PROTOCOL_OPEN, build_tutor_prompt

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo_fixture(dst_repo: Path) -> None:
    dst_repo.mkdir()
    for rel in ["tools", "xyzgl", "curriculum", "snapshots"]:
        src = REPO_ROOT / rel
        dst = dst_repo / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            raise AssertionError(f"missing fixture source: {src}")


def _latest_run_report(repo: Path) -> dict:
    run_dir = sorted((repo / "runs").iterdir())[-1]
    return json.loads((run_dir / "prompt_snapshot_report.json").read_text(encoding="utf-8"))


def test_no_protocol_no_grounding_case_really_omits_protocol_and_grounding_blocks() -> None:
    prompt, meta = build_tutor_prompt(
        "fit-up is uneven, should I keep tacking?",
        cfg=XYZGLConfig(protocol_reground_every=0, grounding_mode="off"),
        turn_index=1,
    )

    assert meta.protocol_regrounded is False
    assert meta.grounding_enabled is False
    assert PROTOCOL_OPEN not in prompt
    assert GROUNDING_OPEN not in prompt


def test_prompt_snapshot_guard_updates_baseline_with_true_no_protocol_case(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _copy_repo_fixture(repo)

    proc = subprocess.run(
        [sys.executable, "tools/prompt_snapshot_guard.py", "--issue", "ISSUE-20260319-126", "--update"],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _latest_run_report(repo)
    assert report["overall"] == "PASS"
    case = report["cases"]["no_protocol_no_grounding"]
    assert case["meta"] == {"protocol_regrounded": False, "grounding_enabled": False}

    baseline = json.loads((repo / "snapshots" / "prompt_snapshots.json").read_text(encoding="utf-8"))
    assert baseline["cases"]["no_protocol_no_grounding"]["meta"] == {
        "protocol_regrounded": False,
        "grounding_enabled": False,
    }
