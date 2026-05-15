from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = REPO_ROOT / "workflow" / "scripts" / "window_workflow_layout.py"
CONFIG_PATH = REPO_ROOT / "workflow" / "config" / "windows.json"
REPORT_PATH = REPO_ROOT / "workflow" / "source" / "XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v27_20260309_120450.md"
CYCLE_SEED_PATH = REPO_ROOT / "workflow" / "state" / "cycle-seed.json"


def _load_layout_module():
    spec = importlib.util.spec_from_file_location("window_workflow_layout", LAYOUT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_window_topology_matches_18_window_design() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    windows = config["windows"]

    assert len(windows) == 18

    workers = [entry for entry in windows if entry["kind"] == "worker"]
    precompilers = [entry for entry in windows if entry["kind"] == "precompile"]
    finals = [entry for entry in windows if entry["kind"] == "final"]

    assert [entry["window"] for entry in workers] == list(range(1, 16))
    assert [entry["window"] for entry in precompilers] == [16, 17]
    assert [entry["window"] for entry in finals] == [18]
    assert precompilers[0]["upstreams"] == [1, 2, 3, 4, 5, 6, 7]
    assert precompilers[1]["upstreams"] == [8, 9, 10, 11, 12, 13, 14, 15]
    assert finals[0]["upstreams"] == [16, 17]


def test_bug_assignment_is_complete_disjoint_and_rebalanced() -> None:
    layout = _load_layout_module()
    bugs = layout.parse_bug_sections(REPORT_PATH.read_text(encoding="utf-8"))
    layout.validate_bug_assignments(bugs)

    counts = Counter(layout.assign_window(bug) for bug in bugs)
    assert counts == {
        1: 13,
        2: 11,
        3: 10,
        4: 10,
        5: 10,
        6: 12,
        7: 11,
        8: 8,
        9: 8,
        10: 5,
        11: 12,
        12: 15,
        13: 9,
        14: 10,
        15: 5,
    }


def test_cycle_seed_state_starts_empty_for_cycle_one() -> None:
    payload = json.loads(CYCLE_SEED_PATH.read_text(encoding="utf-8-sig"))
    assert payload == {
        "active_cycle": 1,
        "seed_package_dir": None,
        "seed_source_window": None,
        "seed_round": None,
        "seed_kind": None,
        "seed_prepared_utc": None,
        "seed_source_final_package_dir": None,
        "seed_backward_sync_dir": None,
        "seed_backward_sync_zip": None,
        "seed_ready_repo_dir": None,
        "seed_ready_repo_zip": None,
    }
