from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.mirror import run_mirror_prediction
from xyzgl.router import route_turn


def test_route_turn_treats_empty_mirror_reply_as_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_FAULT_MODE", "empty")
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="fault",
        enable_mirror=True,
        max_chars_out=256,
    )

    out = route_turn("How do I hold a tighter arc?", cfg=cfg, seed=7)

    assert out["reply"]
    assert "mirror_prediction" not in out
    assert "mirror_meta" not in out
    assert out["backend_error"] == "mirror_backend_contract_error: empty_reply"


def test_run_mirror_prediction_treats_empty_reply_as_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_FAULT_MODE", "empty")

    cfg = XYZGLConfig(
        mirror_backend="fault",
        enable_mirror=True,
        max_chars_out=256,
    )

    text, meta = run_mirror_prediction(
        cfg=cfg,
        seed=11,
        node_title="Arc Length",
        teaching_block="Keep the electrode close and steady.",
        question="What should I watch for?",
    )

    assert text is None
    assert meta == {"error": "mirror_backend_contract_error: empty_reply"}


def test_strict_empty_mirror_reply_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAEDALUS_REQUIRE_REAL_BACKENDS", "1")
    monkeypatch.setenv("DAEDALUS_FAULT_MODE", "empty")

    cfg = XYZGLConfig(
        tutor_backend="stub",
        mirror_backend="fault",
        enable_mirror=True,
        max_chars_out=256,
    )

    with pytest.raises(RuntimeError, match="mirror_backend_contract_error: empty_reply"):
        route_turn("What changes when my arc gets too long?", cfg=cfg, seed=13)

    with pytest.raises(RuntimeError, match="mirror_backend_contract_error: empty_reply"):
        run_mirror_prediction(
            cfg=cfg,
            seed=13,
            node_title="Arc Length",
            teaching_block="Watch the puddle and keep the arc compact.",
            question="What does a long arc sound like?",
        )
