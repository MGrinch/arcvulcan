from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.mirror import run_mirror_prediction


_BAD_PATTERNS = (
    r"\bSafety first:\b",
    r"\bStop and correct\b",
    r"\bShare:\b",
    r"\byou should\b",
    r"\bmake sure\b",
    r"\bremember to\b",
)


def _assert_learner_shaped(text: str) -> None:
    lower = text.lower()
    assert lower.startswith(("i think", "my guess is", "i might be reading it as")), text
    for pattern in _BAD_PATTERNS:
        assert re.search(pattern, text, re.IGNORECASE) is None, text


def test_bug04_stub_mirror_uses_tentative_first_person_language_in_sanitized_mode() -> None:
    cfg = XYZGLConfig(mirror_backend="stub", enable_mirror=True, mirror_send_user_content=True)

    text, meta = run_mirror_prediction(
        cfg=cfg,
        seed=7,
        node_title="Fit-up and Tacking",
        teaching_block=(
            "Safety first: Correct fit-up first. Uneven edges or a changing root opening make the weld inconsistent."
        ),
        question="Q: What seems most likely to be causing the uneven bead?",
    )

    assert meta is not None
    assert meta["backend"] == "mirror_stub"
    assert meta["model"] == "stub"
    assert meta["prompt_mode"] == "sanitized"
    assert text is not None
    _assert_learner_shaped(text)
    assert "fit-up" in text.lower() or "gap" in text.lower()


def test_bug04_stub_mirror_stays_nonimperative_when_context_is_redacted() -> None:
    cfg = XYZGLConfig(mirror_backend="stub", enable_mirror=True, mirror_send_user_content=False)

    text, meta = run_mirror_prediction(
        cfg=cfg,
        seed=11,
        node_title="Arc Length",
        teaching_block="Safety first: Keep the electrode close and watch the puddle.",
        question="Q: What does a long arc usually do to the weld?",
    )

    assert meta is not None
    assert meta["backend"] == "mirror_stub"
    assert meta["model"] == "stub"
    assert meta["prompt_mode"] == "redacted"
    assert text is not None
    _assert_learner_shaped(text)
    assert "share:" not in text.lower()
