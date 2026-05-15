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

ISSUE_ID = "ISSUE-20260321-090"

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


def _write_turn_bundle(tmp_path: Path, *, run_issue: str = ISSUE_ID, summary_issue: str = ISSUE_ID) -> Path:
    turn_report_path = tmp_path / "turn_report.json"
    turn_report_path.write_text(json.dumps(_wrapped_turn_doc(), indent=2), encoding="utf-8")
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "run_id": "turn-source-run",
                "issue_id": run_issue,
                "seed": 7,
                "deterministic": True,
                "outputs": ["turn_report.json", "turn_summary.md", "run.json"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (tmp_path / "turn_summary.md").write_text(
        "\n".join(
            [
                "# Turn Summary — PASS",
                "",
                f"- issue: `{summary_issue}`",
                "- seed: `7`",
                "",
                "## Routed Input",
                "",
                "```text",
                BASE_TURN_RESULT["input"],
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return turn_report_path


def _stub_route_turn(user_input: str, *, seed: int | None, cfg, turn_index: int) -> dict:
    assert user_input == BASE_TURN_RESULT["input"]
    assert seed == 7
    assert turn_index == 0
    replayed = copy.deepcopy(BASE_TURN_RESULT)
    replayed["config"] = dict(cfg.__dict__)
    return replayed


def test_repro_replay_diff_accepts_turn_bundle_when_issue_identity_matches_everywhere(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = _write_turn_bundle(tmp_path)
    monkeypatch.setattr(replay_diff, "route_turn", _stub_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(report_path, strict=False, issue=ISSUE_ID)

    assert status == ("PASS", 0)
    assert problems == []
    assert seed_out == 7
    assert diff["bundle_crosscheck"]["issue_identities"]["observed_issue_ids"] == {
        "cli": ISSUE_ID,
        "run.json": ISSUE_ID,
        "turn_report.json.witness.issue_id": ISSUE_ID,
        "turn_summary.md": ISSUE_ID,
    }


def test_repro_replay_diff_fails_when_sibling_run_json_issue_id_drifts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = _write_turn_bundle(tmp_path, run_issue="ISSUE-20260321-999")
    monkeypatch.setattr(replay_diff, "route_turn", _stub_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(report_path, strict=False, issue=ISSUE_ID)

    assert status == ("FAIL", 1)
    assert seed_out == 7
    assert "run.json: issue_id mismatch: expected ISSUE-20260321-090 got ISSUE-20260321-999" in problems
    assert diff["bundle_crosscheck"]["issue_identities"]["observed_issue_ids"]["run.json"] == "ISSUE-20260321-999"
