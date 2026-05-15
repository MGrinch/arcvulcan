from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.tutor_phases import run_eval_phase, run_probe_phase, run_teach_phase


def _teach_phase() -> object:
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


def test_tutor_phases_fall_back_to_stub_when_real_backends_are_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.delenv("DAEDALUS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    cfg = XYZGLConfig(tutor_backend="gemini", tutor_model="gemini-2.0-flash", max_chars_out=256)

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
    assert probe.question == "Q: Why does a long arc make the weld worse?"
    assert probe.prompt_meta["tutor_backend"] == "stub"
    assert probe.prompt_meta["backend_error"].startswith("tutor_backend_config_error: Missing Gemini API key")

    evaluation = run_eval_phase(
        cfg=cfg,
        seed=11,
        turn_index=3,
        node_id="arc-length",
        node_title="Arc Length",
        teach=_teach_phase(),
        mirror_answer=None,
        user_answer="The puddle gets less stable and the arc spreads out.",
        required_keywords=["arc", "stability"],
    )

    assert evaluation.evaluation
    assert evaluation.prompt_meta["tutor_backend"] == "stub"
    assert evaluation.prompt_meta["backend_error"].startswith("tutor_backend_config_error: Missing Gemini API key")


def test_tutor_phases_raise_when_real_backends_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAEDALUS_REQUIRE_REAL_BACKENDS", "1")
    monkeypatch.delenv("DAEDALUS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    cfg = XYZGLConfig(tutor_backend="gemini", tutor_model="gemini-2.0-flash", max_chars_out=256)

    with pytest.raises(RuntimeError, match="Missing Gemini API key"):
        run_probe_phase(
            cfg=cfg,
            seed=13,
            turn_index=4,
            node_id="arc-length",
            node_title="Arc Length",
            node_summary="Keep the arc short and steady.",
            user_state="novice",
            pointed_question="Why does a long arc make the weld worse?",
        )
