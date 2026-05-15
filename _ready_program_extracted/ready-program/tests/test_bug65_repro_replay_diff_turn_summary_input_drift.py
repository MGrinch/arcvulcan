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

ISSUE_ID = "ISSUE-20260319-065"


def _turn_report(input_text: str) -> dict:
    return {
        "schema_version": "turn_report@1",
        "config": dict(
            replay_diff.XYZGLConfig(
                tutor_backend="stub",
                mirror_backend="stub",
                enable_mirror=False,
                grounding_mode="off",
            ).__dict__
        ),
        "input": input_text,
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
        "tutor_meta": {"backend": "stub", "model": "stub", "latency_ms": 0},
    }


def _write_turn_bundle(tmp_path: Path, *, input_text: str, summary_input: str) -> Path:
    report_path = tmp_path / "turn_report.json"
    report_path.write_text(json.dumps(_turn_report(input_text), indent=2), encoding="utf-8")
    (tmp_path / "turn_summary.md").write_text(
        "\n".join(
            [
                "# Turn Summary — PASS",
                "",
                f"- issue: `{ISSUE_ID}`",
                "- seed: `7`",
                "",
                "## Routed Input",
                "",
                "```text",
                summary_input,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path


def _stub_route_turn(input_text: str, *, seed: int | None, cfg, turn_index: int) -> dict:
    del seed, cfg, turn_index
    return {
        "reply": "Clamp both ends, alternate tacks, and re-check root opening before welding out.",
        "backend": "stub",
        "prompt_meta": {"grounding_enabled": False},
        "input": input_text,
    }


def test_repro_replay_diff_accepts_canonical_routed_input_summary(tmp_path: Path, monkeypatch) -> None:
    report_path = _write_turn_bundle(
        tmp_path,
        input_text="How do I keep my tack sequence from pulling the joint out of alignment?",
        summary_input="How do I keep my tack sequence from pulling the joint out of alignment?",
    )
    monkeypatch.setattr(replay_diff, "route_turn", _stub_route_turn)

    status, problems, diff, seed_out = replay_diff._check_turn_report(report_path, strict=False, issue=ISSUE_ID)

    assert status == ("PASS", 0)
    assert problems == []
    assert seed_out == 7
    assert diff["bundle_crosscheck"]["turn_summary_heading"] == "## Routed Input"


def test_repro_replay_diff_fails_when_turn_summary_routed_input_drifts(tmp_path: Path, monkeypatch) -> None:
    report_path = _write_turn_bundle(
        tmp_path,
        input_text="How do I keep my tack sequence from pulling the joint out of alignment?",
        summary_input="How do I keep my tack sequence from walking out of alignment?",
    )
    monkeypatch.setattr(replay_diff, "route_turn", _stub_route_turn)

    status, problems, diff, _seed_out = replay_diff._check_turn_report(report_path, strict=False, issue=ISSUE_ID)

    assert status == ("FAIL", 1)
    assert any(problem.startswith("turn_summary.md: input mismatch:") for problem in problems)
    assert diff["bundle_crosscheck"]["turn_summary_heading"] == "## Routed Input"


def test_repro_replay_diff_accepts_canonical_truncated_turn_summary_input(tmp_path: Path, monkeypatch) -> None:
    input_text = "Heat " + ("A" * (replay_diff.MAX_ARTIFACT_INPUT_CHARS + 50))
    expected_summary_input = replay_diff._truncate_text(input_text, max_chars=replay_diff.MAX_ARTIFACT_INPUT_CHARS)
    report_path = _write_turn_bundle(tmp_path, input_text=input_text, summary_input=expected_summary_input)
    monkeypatch.setattr(replay_diff, "route_turn", _stub_route_turn)

    status, problems, diff, _seed_out = replay_diff._check_turn_report(report_path, strict=False, issue=ISSUE_ID)

    assert status == ("PASS", 0)
    assert problems == []
    assert diff["bundle_crosscheck"]["expected_turn_summary_input"]["sha256"] == replay_diff._stable_hash(expected_summary_input)
