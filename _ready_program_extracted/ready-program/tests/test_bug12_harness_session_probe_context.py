from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from tools.harness_session import _simulated_user_answer


def test_simulated_user_answer_attempt_zero_is_question_aware_and_incomplete() -> None:
    question_a = "Q: What sets arc length in SMAW?"
    question_b = "Q: Why does arc length change bead shape?"

    answer_a = _simulated_user_answer(
        "smaw_basic_arc",
        question_a,
        ["arc", "length"],
        seed=1337,
        attempt_index=0,
        prior_questions=[],
        prior_answers=[],
    )
    answer_b = _simulated_user_answer(
        "smaw_basic_arc",
        question_b,
        ["arc", "length"],
        seed=1337,
        attempt_index=0,
        prior_questions=[],
        prior_answers=[],
    )

    assert answer_a != answer_b
    assert "arc" in answer_a.lower() or "length" in answer_a.lower()
    assert not ({"arc", "length"} <= set(answer_a.lower().split()))


def test_simulated_user_answer_changes_when_probe_history_changes() -> None:
    prior_questions = [
        "Q: In your own words, what is the key point of Fit-up and tacking discipline?",
    ]
    prior_answers = ["fit."]

    answer_without_history = _simulated_user_answer(
        "fitup_tacking",
        "Q2: What is the missing step in your reasoning?",
        ["fit", "gap", "tack"],
        seed=7,
        attempt_index=1,
        prior_questions=[],
        prior_answers=[],
    )
    answer_with_history = _simulated_user_answer(
        "fitup_tacking",
        "Q2: What is the missing step in your reasoning?",
        ["fit", "gap", "tack"],
        seed=7,
        attempt_index=1,
        prior_questions=prior_questions,
        prior_answers=prior_answers,
    )

    assert answer_with_history != answer_without_history
    assert "follow-up question changed my focus" in answer_with_history.lower()
