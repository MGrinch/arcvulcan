from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from json_canon import dumps_canonical
import property_turn_fuzzer


ISSUE_ID = "ISSUE-20260321-034"


def test_property_turn_fuzzer_run_meta_marks_builtin_mode_as_truthfully_deterministic() -> None:
    run_meta = property_turn_fuzzer._run_meta(
        run_id="run-34",
        issue=ISSUE_ID,
        seed=34,
        overall="PASS",
        mode="builtin",
        cases=12,
        problems=0,
        results_dropped=0,
        problems_dropped=0,
        max_len_requested=128,
        max_len_effective=128,
        max_case_len_seen=64,
        runtime_context={"tutor_backend": "stub"},
    )

    assert run_meta["tool"] == "property_turn_fuzzer"
    assert run_meta["mode"] == "builtin"
    assert run_meta["overall"] == "PASS"
    assert run_meta["deterministic"] is True
    assert run_meta["artifact_identity_stable"] is False
    assert run_meta["artifact_content_stable"] is True
    assert "builtin property fuzzing" in run_meta["determinism_basis"]
    assert run_meta["observed"]["cases_executed"] == 12
    assert run_meta["observed"]["problems"] == 0


def test_property_turn_fuzzer_run_meta_marks_hypothesis_execution_as_nondeterministic() -> None:
    run_meta = property_turn_fuzzer._run_meta(
        run_id="run-34",
        issue=ISSUE_ID,
        seed=34,
        overall="FAIL",
        mode="hypothesis",
        cases=12,
        problems=1,
        results_dropped=2,
        problems_dropped=0,
        max_len_requested=128,
        max_len_effective=64,
        max_case_len_seen=64,
        runtime_context={"tutor_backend": "stub"},
    )

    assert run_meta["mode"] == "hypothesis"
    assert run_meta["overall"] == "FAIL"
    assert run_meta["deterministic"] is False
    assert run_meta["artifact_identity_stable"] is False
    assert run_meta["artifact_content_stable"] is False
    assert "Hypothesis-driven exploration" in run_meta["determinism_basis"]
    assert run_meta["observed"]["results_dropped"] == 2


def test_property_turn_fuzzer_run_bundle_is_canonical_and_exposes_truthful_run_contract(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "property_turn_fuzzer.py"),
            "--issue",
            ISSUE_ID,
            "--seed",
            "34",
            "--cases",
            "3",
            "--max-len",
            "24",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    assert run_dirs
    run_json_path = run_dirs[-1] / "run.json"
    raw_text = run_json_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    assert raw_text == dumps_canonical(data)
    assert data["tool"] == "property_turn_fuzzer"
    assert data["mode"] == "builtin"
    assert data["deterministic"] is True
    assert data["artifact_identity_stable"] is False
    assert data["artifact_content_stable"] is True
    assert "builtin property fuzzing" in data["determinism_basis"]
    assert data["observed"]["cases_executed"] == 3
    assert data["observed"]["problems"] == 0
