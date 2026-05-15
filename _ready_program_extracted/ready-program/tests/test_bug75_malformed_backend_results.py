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
from xyzgl.router import route_turn


class _NoneResultBackend:
    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None):
        return None


class _MissingBackendFieldResult:
    text = "Tutor replied:\nKeep the arc short and steady.\nQuestion: What should you watch first?"
    model = "faulty"
    latency_ms = 7


class _MissingBackendFieldBackend:
    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None):
        return _MissingBackendFieldResult()


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


def test_route_turn_treats_missing_result_as_backend_contract_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from xyzgl import router as router_mod

    original_get_tutor_backend = router_mod.get_tutor_backend

    def fake_get_tutor_backend(cfg: XYZGLConfig):
        if cfg.tutor_backend == "malformed-none":
            return _NoneResultBackend()
        return original_get_tutor_backend(cfg)

    monkeypatch.setattr(router_mod, "get_tutor_backend", fake_get_tutor_backend)
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    cfg = XYZGLConfig(tutor_backend="malformed-none", max_chars_out=256)
    out = route_turn("How do I keep my arc tighter?", cfg=cfg, seed=5)

    assert out["reply"]
    assert out["backend"] == "stub"
    assert out["tutor_meta"]["backend"] == "stub"
    assert out["backend_error"] == "tutor_backend_contract_error: missing_result"
    assert out["prompt_meta"]["backend_error"] == "tutor_backend_contract_error: missing_result"



def test_tutor_phases_treat_missing_backend_field_as_backend_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
    teach_phase: object,
) -> None:
    from xyzgl.orchestrator import tutor_phases as tutor_phases_mod

    monkeypatch.setattr(tutor_phases_mod, "_get_tutor", lambda cfg: _MissingBackendFieldBackend())
    monkeypatch.delenv("DAEDALUS_REQUIRE_REAL_BACKENDS", raising=False)
    monkeypatch.setenv("DAEDALUS_EXPOSE_BACKEND_ERRORS", "1")

    cfg = XYZGLConfig(tutor_backend="fault", max_chars_out=256)

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
    assert probe.prompt_meta["backend_error"] == "tutor_backend_contract_error: missing_field:backend:AttributeError"

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
    assert evaluation.prompt_meta["tutor_backend"] == "stub"
    assert evaluation.prompt_meta["backend_error"] == "tutor_backend_contract_error: missing_field:backend:AttributeError"



def test_strict_malformed_backend_results_raise_contract_errors(
    monkeypatch: pytest.MonkeyPatch,
    teach_phase: object,
) -> None:
    from xyzgl import router as router_mod
    from xyzgl.orchestrator import tutor_phases as tutor_phases_mod

    original_get_tutor_backend = router_mod.get_tutor_backend

    def fake_get_tutor_backend(cfg: XYZGLConfig):
        if cfg.tutor_backend == "malformed-none":
            return _NoneResultBackend()
        return original_get_tutor_backend(cfg)

    monkeypatch.setattr(router_mod, "get_tutor_backend", fake_get_tutor_backend)
    monkeypatch.setattr(tutor_phases_mod, "_get_tutor", lambda cfg: _MissingBackendFieldBackend())
    monkeypatch.setenv("DAEDALUS_REQUIRE_REAL_BACKENDS", "1")

    with pytest.raises(RuntimeError, match="tutor_backend_contract_error: missing_result"):
        route_turn("Why is my arc wandering?", cfg=XYZGLConfig(tutor_backend="malformed-none", max_chars_out=256), seed=13)

    with pytest.raises(RuntimeError, match="tutor_backend_contract_error: missing_field:backend:AttributeError"):
        run_probe_phase(
            cfg=XYZGLConfig(tutor_backend="fault", max_chars_out=256),
            seed=17,
            turn_index=2,
            node_id="arc-length",
            node_title="Arc Length",
            node_summary="Keep the arc short and steady.",
            user_state="novice",
            pointed_question="Why does a long arc make the weld worse?",
        )

    with pytest.raises(RuntimeError, match="tutor_backend_contract_error: missing_field:backend:AttributeError"):
        run_eval_phase(
            cfg=XYZGLConfig(tutor_backend="fault", max_chars_out=256),
            seed=19,
            turn_index=3,
            node_id="arc-length",
            node_title="Arc Length",
            teach=teach_phase,
            mirror_answer=None,
            user_answer="The puddle gets less stable and the arc spreads out.",
            required_keywords=["arc", "stability"],
        )
