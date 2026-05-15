from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from witness.core import WitnessCore


def test_witness_core_replaces_lone_surrogates_before_json_write(tmp_path: Path) -> None:
    out_path = tmp_path / "turn_report.json"
    event = WitnessCore().make_event(
        "ISSUE-20260318-010",
        {"turn_result": {"bad\ud800key": "value\ud800tail", "list": ["ok", "more\ud800bad"]}},
    )

    WitnessCore().write_event_json(event, str(out_path))

    data = json.loads(out_path.read_text(encoding="utf-8"))
    turn_result = data["payload"]["turn_result"]
    assert turn_result["bad?key"] == "value?tail"
    assert turn_result["list"] == ["ok", "more?bad"]
    assert "\ud800" not in out_path.read_text(encoding="utf-8")
