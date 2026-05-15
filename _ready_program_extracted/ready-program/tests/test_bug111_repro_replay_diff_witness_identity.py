from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import repro_replay_diff as replay_diff
from witness.core import WitnessCore

ISSUE_ID = "ISSUE-20260319-111"

BASE_TURN_RESULT = {
    "schema_version": "turn_report@1",
    "config": dict(
        replay_diff.XYZGLConfig(
            tutor_backend="stub",
            mirror_backend="stub",
            enable_mirror=False,
            grounding_mode="off",
        ).__dict__
    ),
    "input": "How do I keep my tack sequence from pulling the joint out of alignment?",
    "reply": "Clamp both ends, alternate tacks, and re-check root opening before welding out.",
    "backend": "stub",
    "prompt_meta": {"grounding_enabled": False},
    "seed": 7,
    "turn_index": 0,
    "mirror_prediction": None,
    "mirror_meta": None,
    "backend_error": None,
    "requested_backend": "stub",
    "effective_backend": "stub",
    "tutor_meta": {"backend": "stub", "model": "stub-model", "latency_ms": 0},
}


def _wrapped_turn_doc(turn_result: dict | None = None) -> dict:
    payload = {"turn_result": copy.deepcopy(turn_result or BASE_TURN_RESULT)}
    event = WitnessCore().make_event(ISSUE_ID, payload)
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "issue_id": event.issue_id,
        "created_at": event.created_at,
        "payload": event.payload,
    }


def test_repro_replay_diff_strict_accepts_canonical_wrapped_turn_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    turn_report_path = tmp_path / "turn_report.json"
    turn_report_path.write_text(json.dumps(_wrapped_turn_doc(), indent=2), encoding="utf-8")

    def fake_route_turn(user_input: str, *, seed: int, cfg, turn_index: int) -> dict:
        assert user_input == BASE_TURN_RESULT["input"]
        assert seed == 7
        assert turn_index == 0
        replayed = copy.deepcopy(BASE_TURN_RESULT)
        replayed["config"] = dict(cfg.__dict__)
        return replayed

    monkeypatch.setattr(replay_diff, "route_turn", fake_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(
        turn_report_path,
        strict=True,
        issue=ISSUE_ID,
    )

    assert status == ("PASS", 0)
    assert problems == []
    assert seed_out == 7
    assert diff["expected"]["witness_envelope"]["sha256"] == diff["replayed"]["witness_envelope"]["sha256"]


@pytest.mark.parametrize(
    ("mutator", "expected_fragment"),
    [
        (lambda doc: doc.__setitem__("issue_id", "ISSUE-20260319-999"), "mismatch witness.issue_id:"),
        (lambda doc: doc.__setitem__("event_id", "EVT-forged111"), "mismatch witness.event_id:"),
        (lambda doc: doc.__setitem__("created_at", "1970-01-01T00:00:01Z"), "mismatch witness.created_at:"),
        (lambda doc: doc["payload"]["turn_result"].__setitem__("turn_index", 1), "turn_report.json: mismatch turn_index:"),
    ],
)
def test_repro_replay_diff_strict_rejects_wrapped_turn_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    expected_fragment: str,
) -> None:
    doc = _wrapped_turn_doc()
    mutator(doc)
    turn_report_path = tmp_path / "turn_report.json"
    turn_report_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def fake_route_turn(user_input: str, *, seed: int, cfg, turn_index: int) -> dict:
        assert user_input == BASE_TURN_RESULT["input"]
        assert seed == 7
        replayed = copy.deepcopy(BASE_TURN_RESULT)
        replayed["config"] = dict(cfg.__dict__)
        replayed["turn_index"] = 0
        return replayed

    monkeypatch.setattr(replay_diff, "route_turn", fake_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(
        turn_report_path,
        strict=True,
        issue=ISSUE_ID,
    )

    assert status == ("FAIL", 1)
    assert seed_out == 7
    assert any(expected_fragment in problem for problem in problems)
    assert diff["expected"]["witness_envelope"]["sha256"] != diff["replayed"]["witness_envelope"]["sha256"] or expected_fragment.endswith("turn_index:")
