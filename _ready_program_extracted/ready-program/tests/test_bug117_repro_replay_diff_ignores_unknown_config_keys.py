from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import repro_replay_diff as replay_diff

ISSUE_ID = "ISSUE-20260315-117"


def test_repro_replay_diff_strict_ignores_unknown_config_keys(tmp_path: Path, monkeypatch) -> None:
    turn_report_path = tmp_path / "turn_report.json"
    stored_config = dict(replay_diff.XYZGLConfig().__dict__)
    stored_config["future_flag"] = "ignored-by-runtime"
    turn_report = {
        "schema_version": "turn_report@1",
        "config": stored_config,
        "input": "How do I tack this evenly?",
        "reply": "Trim the joint, align the gap, then re-tack at consistent spacing.",
        "backend": "stub",
        "prompt_meta": {"grounding_enabled": False},
        "seed": 1,
        "turn_index": 0,
        "mirror_prediction": None,
        "mirror_meta": None,
        "backend_error": None,
        "requested_backend": "stub",
        "effective_backend": "stub",
        "tutor_meta": {"backend": "stub"},
    }
    turn_report_path.write_text(json.dumps(turn_report, indent=2), encoding="utf-8")

    def fake_route_turn(user_input: str, *, seed: int, cfg, turn_index: int) -> dict:
        assert user_input == turn_report["input"]
        assert seed == 1
        assert turn_index == 0
        return {
            "reply": turn_report["reply"],
            "backend": turn_report["backend"],
            "prompt_meta": turn_report["prompt_meta"],
            "config": dict(cfg.__dict__),
            "turn_index": turn_index,
            "mirror_prediction": None,
            "mirror_meta": None,
            "backend_error": None,
            "requested_backend": "stub",
            "effective_backend": "stub",
            "tutor_meta": {"backend": "stub"},
        }

    monkeypatch.setattr(replay_diff, "route_turn", fake_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(
        turn_report_path,
        strict=True,
        issue=ISSUE_ID,
    )

    assert status == ("PASS", 0)
    assert problems == []
    assert seed_out == 1
    assert "future_flag" not in diff["expected"]["config"]["keys_sample"]
    assert "future_flag" not in diff["replayed"]["config"]["keys_sample"]
    assert diff["expected"]["config"]["sha256"] == diff["replayed"]["config"]["sha256"]
