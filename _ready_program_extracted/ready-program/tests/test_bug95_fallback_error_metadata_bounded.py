from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.mirror import run_mirror_prediction
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.tutor_phases import run_eval_phase, run_probe_phase, run_teach_phase
from xyzgl.router import route_turn


_MAX_OUT = 96
_SECRET = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"
_RAW_TOKEN = "top-secret-token"


class _OversizedTutorErrorBackend:
    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None):
        raise RuntimeError(
            "backend exploded Authorization: Bearer "
            + _SECRET
            + " url=https://example.invalid/path?token="
            + _RAW_TOKEN
            + " payload="
            + ("X" * 600)
        )


class _OversizedMirrorErrorBackend:
    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None):
        raise RuntimeError(
            "mirror exploded Authorization: Bearer "
            + _SECRET
            + " url=https://mirror.invalid/path?token="
            + _RAW_TOKEN
            + " payload="
            + ("Y" * 600)
        )


@pytest.fixture
def teach_phase() -> object:
    return run_teach_phase(
        cfg=XYZGLConfig(),
        seed=3,
        turn_index=1,
        node_id="arc-length",
        node_title="Arc Length",
        node_summary="Keep the arc short and steady.",
        user_state="novice",
        budget=TeachingBudget(min_sentences=1, max_sentences=2, density="light"),
    )


def _assert_bounded_and_sanitized(value: str) -> None:
    assert value
    assert len(value) <= _MAX_OUT
    assert _SECRET not in value
    assert _RAW_TOKEN not in value
    assert "<redacted>" in value


def test_route_turn_bounds_fallback_backend_error_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from xyzgl import router as router_mod

    original_get_tutor_backend = router_mod.get_tutor_backend

    def fake_get_tutor_backend(cfg: XYZGLConfig):
        if cfg.tutor_backend == "oversized-error":
            return _OversizedTutorErrorBackend()
        return original_get_tutor_backend(cfg)

    monkeypatch.setattr(router_mod, "get_tutor_backend", fake_get_tutor_backend)
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    out = route_turn(
        "How do I keep my arc tighter?",
        cfg=XYZGLConfig(tutor_backend="oversized-error", max_chars_out=_MAX_OUT),
        seed=5,
    )

    assert out["reply"]
    assert out["backend"] == "stub"
    assert out["tutor_meta"]["backend"] == "stub"
    _assert_bounded_and_sanitized(out["backend_error"])
    _assert_bounded_and_sanitized(out["prompt_meta"]["backend_error"])



def test_tutor_phase_prompt_meta_bounds_fallback_backend_error(
    monkeypatch: pytest.MonkeyPatch,
    teach_phase: object,
) -> None:
    from xyzgl.orchestrator import tutor_phases as tutor_phases_mod

    monkeypatch.setattr(tutor_phases_mod, "_get_tutor", lambda cfg: _OversizedTutorErrorBackend())
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    cfg = XYZGLConfig(tutor_backend="fault", max_chars_out=_MAX_OUT)

    probe = run_probe_phase(
        cfg=cfg,
        seed=7,
        turn_index=2,
        node_id="arc-length",
        node_title="Arc Length",
        node_summary="Keep the arc short and steady.",
        user_state="novice",
        pointed_question="Why does a long arc make the weld worse?",
    )

    assert probe.teaching_block
    _assert_bounded_and_sanitized(probe.prompt_meta["backend_error"])

    evaluation = run_eval_phase(
        cfg=cfg,
        seed=11,
        turn_index=3,
        node_id="arc-length",
        node_title="Arc Length",
        teach=teach_phase,
        mirror_answer=None,
        user_answer="The puddle gets less stable and the arc spreads out.",
        required_keywords=["arc", "stability"],
    )

    assert evaluation.evaluation
    _assert_bounded_and_sanitized(evaluation.prompt_meta["backend_error"])



def test_run_mirror_prediction_bounds_runtime_error_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from xyzgl.orchestrator import mirror as mirror_mod

    monkeypatch.setattr(mirror_mod, "get_mirror_backend", lambda cfg: _OversizedMirrorErrorBackend())
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)

    text, meta = run_mirror_prediction(
        cfg=XYZGLConfig(mirror_backend="fault", enable_mirror=True, max_chars_out=_MAX_OUT),
        seed=13,
        node_title="Arc Length",
        teaching_block="Keep the electrode close and steady.",
        question="What should I watch for?",
    )

    assert text is None
    assert meta is not None
    _assert_bounded_and_sanitized(meta["error"])
