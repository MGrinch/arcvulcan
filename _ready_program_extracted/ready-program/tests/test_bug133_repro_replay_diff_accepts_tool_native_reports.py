from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from witness.core import WitnessCore
from xyzgl.config import XYZGLConfig
from xyzgl.knowledge.graph import default_graph
from xyzgl.orchestrator.session_loop import run_session
from xyzgl.router import route_turn

REPRO_REPLAY_DIFF_PATH = REPO_ROOT / "tools" / "repro_replay_diff.py"
_RUN_DIR_RE = re.compile(r"wrote outputs to (?P<path>.+)$")
_ISSUE_ID = "ISSUE-20260318-133"


def _extract_run_dir(stdout: str) -> Path:
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    assert lines, "expected tool stdout to contain a run directory"
    match = _RUN_DIR_RE.search(lines[-1])
    assert match, f"expected final stdout line to contain run dir, got: {lines[-1]!r}"
    return Path(match.group("path")).resolve()


def _turn_report() -> dict:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=False,
        grounding_mode="off",
    )
    result = route_turn("What is a weld?", seed=1337, cfg=cfg, turn_index=0)
    return {
        "schema_version": "turn_report@1",
        "seed": 1337,
        "config": result.get("config") or cfg.__dict__,
        "input": "What is a weld?",
        "reply": result.get("reply"),
        "backend": result.get("backend"),
        "prompt_meta": result.get("prompt_meta"),
        "turn_index": result.get("turn_index", 0),
    }


def _session_report() -> dict:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="stub",
        enable_mirror=False,
        grounding_mode="off",
    )

    def input_provider(prompt: str) -> tuple[str, dict]:
        return ("Arc length affects heat and control.", {"typing_ms": 4500})

    session_report, _graph = run_session(
        session_id="session-bug-133",
        cfg=cfg,
        seed=1337,
        max_turns=1,
        graph=default_graph(),
        input_provider=input_provider,
    )
    return session_report.to_json()


def _wrap_report(payload_key: str, report: dict) -> dict:
    event = WitnessCore().make_event(_ISSUE_ID, {payload_key: report})
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "issue_id": event.issue_id,
        "created_at": event.created_at,
        "payload": event.payload,
    }


def _write_run_dir(run_dir: Path, *, turn_repr: str, session_repr: str) -> None:
    turn_report = _turn_report()
    session_report = _session_report()

    turn_doc = turn_report if turn_repr == "standalone" else _wrap_report("turn_result", turn_report)
    session_doc = session_report if session_repr == "standalone" else _wrap_report("session_report", session_report)

    (run_dir / "turn_report.json").write_text(json.dumps(turn_doc), encoding="utf-8")
    (run_dir / "session_report.json").write_text(json.dumps(session_doc), encoding="utf-8")


@pytest.mark.parametrize(
    ("turn_repr", "session_repr"),
    [
        ("standalone", "standalone"),
        ("standalone", "wrapped"),
        ("wrapped", "standalone"),
        ("wrapped", "wrapped"),
    ],
)
def test_repro_replay_diff_accepts_canonical_reports_in_tool_native_or_witness_wrapped_form(
    tmp_path: Path,
    turn_repr: str,
    session_repr: str,
) -> None:
    source_run_dir = tmp_path / "source-run"
    source_run_dir.mkdir()
    _write_run_dir(source_run_dir, turn_repr=turn_repr, session_repr=session_repr)

    env = {**os.environ, "DAEDALUS_RUNS_DIR": str(tmp_path / "runs")}
    proc = subprocess.run(
        [
            sys.executable,
            str(REPRO_REPLAY_DIFF_PATH),
            "--issue",
            _ISSUE_ID,
            "--allow-external-path",
            str(source_run_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    replay_run_dir = _extract_run_dir(proc.stdout)
    report = json.loads((replay_run_dir / "replay_diff_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "PASS"
    assert report["problems"] == []
    assert Path(report["source"]).resolve() == source_run_dir.resolve()
