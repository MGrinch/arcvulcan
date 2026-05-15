from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.tutor_phases import run_teach_phase
from xyzgl.router import route_turn


def test_route_turn_fails_closed_on_invalid_protocol_path() -> None:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        protocol_path="missing/does_not_exist.md",
        protocol_reground_every=1,
    )

    with pytest.raises(RuntimeError, match="protocol_load_error: missing_or_not_file"):
        route_turn("How do I hold a tighter arc?", cfg=cfg, seed=7)


def test_route_turn_allows_explicit_protocol_fallback_policy() -> None:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        protocol_path="missing/does_not_exist.md",
        protocol_reground_every=1,
        allow_protocol_fallback=True,
    )

    out = route_turn("How do I hold a tighter arc?", cfg=cfg, seed=7)

    assert out["reply"]
    assert out["prompt_meta"]["protocol_loaded"] is False
    assert out["prompt_meta"]["protocol_fallback"] is True
    assert out["prompt_meta"]["protocol_load_error"] == "protocol_load_error: missing_or_not_file"


def test_run_teach_phase_fails_closed_on_invalid_protocol_path() -> None:
    cfg = XYZGLConfig(
        tutor_backend="stub",
        protocol_path="missing/does_not_exist.md",
        protocol_reground_every=1,
    )

    with pytest.raises(RuntimeError, match="protocol_load_error: missing_or_not_file"):
        run_teach_phase(
            cfg=cfg,
            seed=11,
            turn_index=0,
            node_id="node-1",
            node_title="Arc Length",
            node_summary="Keep the arc compact and stable.",
            user_state="learning",
            budget=TeachingBudget(1, 3, "light"),
        )
