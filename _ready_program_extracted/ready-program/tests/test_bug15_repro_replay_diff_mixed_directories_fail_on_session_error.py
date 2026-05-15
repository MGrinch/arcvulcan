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


def test_repro_replay_diff_mixed_directory_fails_when_session_report_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "mixed-run"
    target.mkdir()
    (target / "turn_report.json").write_text("{}", encoding="utf-8")
    (target / "session_report.json").write_text("{}", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(replay_diff, "_run_id", lambda: "bug15-mixed-directory")

    calls: list[tuple[object, ...]] = []

    def _fake_turn(path: Path, *, strict: bool, issue: str):
        calls.append(("turn", path.name, strict, issue))
        return ("PASS", 0), [], {"expected_hash": "turn-ok", "replayed_hash": "turn-ok"}, 7

    def _fake_session(path: Path):
        calls.append(("session", path.name))
        return (
            ("FAIL", 1),
            ["session_report.json: turns mismatch"],
            {"expected_hash": "session-expected", "replayed_hash": "session-replayed"},
            11,
        )

    monkeypatch.setattr(replay_diff, "_check_turn_report", _fake_turn)
    monkeypatch.setattr(replay_diff, "_check_session_report", _fake_session)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repro_replay_diff.py",
            "--issue",
            "ISSUE-20260315-015",
            "--allow-external-path",
            str(target),
        ],
    )

    exit_code = replay_diff.main()

    assert exit_code == 1
    assert calls == [
        ("turn", "turn_report.json", False, "ISSUE-20260315-015"),
        ("session", "session_report.json"),
    ]

    report_paths = sorted(runs_dir.glob("*/replay_diff_report.json"))
    assert report_paths, "expected replay_diff_report.json output"
    report = json.loads(report_paths[-1].read_text(encoding="utf-8"))

    assert report["overall"] == "FAIL"
    assert report["problems"] == ["session_report.json: turns mismatch"]
    assert set(report["diff"].keys()) == {"turn_report", "session_report"}
    assert report["diff"]["turn_report"]["expected_hash"] == "turn-ok"
    assert report["diff"]["session_report"]["replayed_hash"] == "session-replayed"
