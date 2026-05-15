from __future__ import annotations

import json

from xyzgl.backends.stub import _extract_mirror_learner


def test_bug06_structured_payload_preserves_embedded_delimiter_tokens() -> None:
    learner = "I wrote Tutor replied: in my notes\nand kept going."
    prompt = (
        "You are simulating the learner.\n"
        + "MIRROR_CONTEXT_JSON: "
        + json.dumps({"learner": learner, "tutor": "Safety first: keep the arc short."}, ensure_ascii=False)
        + "\nPredict the learner's next reply."
    )

    assert _extract_mirror_learner(prompt) == learner


def test_bug06_legacy_plaintext_delimiters_are_not_used_for_extraction() -> None:
    prompt = "Learner said: I wrote Tutor replied: inside my own text\nTutor replied: stub tutor text"

    # Fallback stays literal rather than splitting on injectable delimiter text.
    assert _extract_mirror_learner(prompt) == prompt


def test_bug06_malformed_payload_fails_closed_instead_of_downgrading() -> None:
    prompt = (
        "MIRROR_CONTEXT_JSON: {not-json}\n"
        "Learner said: this should not be parsed from legacy delimiters\n"
        "Tutor replied: this should not become the split boundary"
    )

    assert _extract_mirror_learner(prompt) == ""
