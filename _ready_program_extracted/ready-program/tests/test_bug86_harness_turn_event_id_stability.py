from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from witness.core import WitnessCore


ISSUE_ID = "ISSUE-20260319-086"


def _make_turn_payload(*, tutor_latency_ms: int, mirror_latency_ms: int, direct_latency_ms: int) -> dict[str, object]:
    return {
        "turn_result": {
            "input": "fit-up is uneven",
            "reply": "Clamp it, check the gap, then tack opposite corners.",
            "seed": 1337,
            "turn_index": 0,
            "backend": "tutor_fault",
            "effective_backend": "tutor_fault",
            "tutor_latency_ms": tutor_latency_ms,
            "tutor_meta": {
                "backend": "tutor_fault",
                "model": "slow",
                "latency_ms": direct_latency_ms,
            },
            "mirror_meta": {
                "backend": "mirror_fault",
                "model": "slow",
                "latency_ms": mirror_latency_ms,
            },
        }
    }


def test_witness_event_id_ignores_latency_jitter_but_preserves_payload() -> None:
    wc = WitnessCore()
    event_a = wc.make_event(
        ISSUE_ID,
        _make_turn_payload(tutor_latency_ms=51, mirror_latency_ms=22, direct_latency_ms=51),
    )
    event_b = wc.make_event(
        ISSUE_ID,
        _make_turn_payload(tutor_latency_ms=97, mirror_latency_ms=44, direct_latency_ms=97),
    )

    assert event_a.event_id == event_b.event_id
    assert event_a.payload["turn_result"]["tutor_meta"]["latency_ms"] == 51
    assert event_b.payload["turn_result"]["tutor_meta"]["latency_ms"] == 97
    assert event_a.payload["turn_result"]["mirror_meta"]["latency_ms"] == 22
    assert event_b.payload["turn_result"]["mirror_meta"]["latency_ms"] == 44


def test_witness_event_id_still_changes_for_semantic_turn_differences() -> None:
    wc = WitnessCore()
    base = _make_turn_payload(tutor_latency_ms=51, mirror_latency_ms=22, direct_latency_ms=51)
    changed = _make_turn_payload(tutor_latency_ms=97, mirror_latency_ms=44, direct_latency_ms=97)
    changed["turn_result"]["reply"] = "Use a bridge clamp before you retack."

    event_a = wc.make_event(ISSUE_ID, base)
    event_b = wc.make_event(ISSUE_ID, changed)

    assert event_a.event_id != event_b.event_id
