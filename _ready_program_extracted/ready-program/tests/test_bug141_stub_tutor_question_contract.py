from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.backends.base import BackendResult
from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.tutor_phases import run_probe_phase, run_teach_phase


class _LongContractReplyBackend:
    name = "contract"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        long_hint = "Keep the arc short and steady. " * 30
        return BackendResult(
            text=f"{long_hint}\nQ: Why does a long arc make the weld worse?",
            backend=self.name,
            model="contract",
            latency_ms=1,
        )


def test_stub_backend_keeps_distinct_teach_and_probe_questions() -> None:
    cfg = XYZGLConfig(tutor_backend="stub", max_chars_out=256)

    teach = run_teach_phase(
        cfg=cfg,
        seed=3,
        turn_index=1,
        node_id="arc-length",
        node_title="Arc Length",
        node_summary="Keep the arc short and steady.",
        user_state="novice",
        budget=TeachingBudget(min_sentences=1, max_sentences=2, density="light"),
    )
    probe = run_probe_phase(
        cfg=cfg,
        seed=5,
        turn_index=2,
        node_id="arc-length",
        node_title="Arc Length",
        node_summary="Keep the arc short and steady.",
        user_state="novice",
        pointed_question="Why does a long arc make the weld worse?",
    )

    assert teach.question.startswith("Q: ")
    assert probe.question == "Q: Why does a long arc make the weld worse?"
    assert teach.question != probe.question
    assert teach.question != "Q: Can you explain your reasoning step by step?"


def test_probe_phase_preserves_question_when_reply_body_is_long(monkeypatch: pytest.MonkeyPatch) -> None:
    from xyzgl.orchestrator import tutor_phases as tutor_phases_mod

    monkeypatch.setattr(tutor_phases_mod, "_get_tutor", lambda cfg: _LongContractReplyBackend())

    probe = run_probe_phase(
        cfg=XYZGLConfig(tutor_backend="contract", max_chars_out=96),
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
