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

ISSUE_ID = "ISSUE-20260315-016"


BASE_TURN_RESULT = {
    "config": dict(
        replay_diff.XYZGLConfig(
            tutor_backend="fault",
            mirror_backend="stub",
            enable_mirror=True,
        ).__dict__
    ),
    "input": "How do I recover when the fit-up shifts during a tack sequence?",
    "reply": "Re-clamp the joint, verify root opening, then re-tack from both ends back toward center.",
    "backend": "stub",
    "prompt_meta": {
        "grounding_enabled": False,
        "backend_error": "tutor_backend_error: simulated fallback",
    },
    "seed": 5,
    "turn_index": 0,
    "mirror_prediction": "Mirror suggests checking fit-up before restarting.",
    "mirror_meta": {
        "backend": "stub",
        "model": "mirror-stub",
        "latency_ms": 0,
        "prompt_mode": "raw",
    },
    "backend_error": "tutor_backend_error: simulated fallback",
    "requested_backend": "fault",
    "effective_backend": "stub",
    "tutor_meta": {
        "backend": "stub",
        "model": "stub-model",
        "latency_ms": 0,
    },
}


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("mirror_prediction", "Forged mirror answer that should not pass replay."),
        (
            "mirror_meta",
            {
                "backend": "stub",
                "model": "forged-mirror",
                "latency_ms": 99,
                "prompt_mode": "redacted",
            },
        ),
        ("backend_error", "forged backend error state"),
        ("requested_backend", "stub"),
        ("effective_backend", "fault"),
        (
            "tutor_meta",
            {
                "backend": "fault",
                "model": "forged-model",
                "latency_ms": 99,
            },
        ),
    ],
)
def test_repro_replay_diff_strict_fails_on_turn_provenance_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    forged_value,
) -> None:
    turn_report_path = tmp_path / "turn_report.json"
    stored_turn_result = copy.deepcopy(BASE_TURN_RESULT)
    stored_turn_result[field] = forged_value
    turn_report_path.write_text(json.dumps(stored_turn_result, indent=2), encoding="utf-8")

    def fake_route_turn(user_input: str, *, seed: int, cfg, turn_index: int) -> dict:
        assert user_input == BASE_TURN_RESULT["input"]
        assert seed == 5
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

    assert status == ("FAIL", 1)
    assert seed_out == 5
    assert any(problem.startswith(f"turn_report.json: mismatch {field}:") for problem in problems)
    assert diff["expected"][field]["sha256"] != diff["replayed"][field]["sha256"]
