from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HARNESS_PATH = REPO_ROOT / "tools" / "harness_session.py"
SEED_SWEEP_PATH = REPO_ROOT / "tools" / "seed_sweep.py"


def _latest_run_json(runs_dir: Path) -> dict:
    run_paths = sorted(runs_dir.glob("*/run.json"))
    assert run_paths, "expected at least one run.json output"
    return json.loads(run_paths[-1].read_text(encoding="utf-8"))


def _latest_report(runs_dir: Path, name: str) -> dict:
    report_paths = sorted(runs_dir.glob(f"*/{name}"))
    assert report_paths, f"expected at least one {name} output"
    return json.loads(report_paths[-1].read_text(encoding="utf-8"))


def test_harness_session_surfaces_real_seed_contracts(tmp_path: Path) -> None:
    det_runs = tmp_path / "det-runs"
    amb_runs = tmp_path / "amb-runs"

    det = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--issue", "ISSUE-20260309-140", "--seed", "1337", "--max-turns", "3"],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(det_runs), "DAEDALUS_ENFORCE_DETERMINISM": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert det.returncode == 0, det.stdout + det.stderr
    det_meta = _latest_run_json(det_runs)
    assert det_meta["execution_mode"] == "deterministic"
    assert det_meta["seed_contract"] == "requested-seed"
    assert det_meta["ambient_root_seed"] is None
    assert det_meta["session_seed"] == 1337
    assert det_meta["simulator_seed"] == 1337

    amb = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--issue", "ISSUE-20260309-140", "--seed", "1337", "--max-turns", "3"],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(amb_runs), "DAEDALUS_ENFORCE_DETERMINISM": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert amb.returncode == 0, amb.stdout + amb.stderr
    amb_meta = _latest_run_json(amb_runs)
    assert amb_meta["execution_mode"] == "ambient"
    assert amb_meta["seed_contract"] == "ambient-root-derived"
    assert isinstance(amb_meta["ambient_root_seed"], int)
    assert isinstance(amb_meta["session_seed"], int)
    assert isinstance(amb_meta["simulator_seed"], int)
    assert amb_meta["session_seed"] != 1337
    assert amb_meta["simulator_seed"] != 1337


def test_seed_sweep_tracks_effective_seeds_when_determinism_disabled(tmp_path: Path) -> None:
    det_runs = tmp_path / "det-sweep"
    amb_runs = tmp_path / "amb-sweep"

    det = subprocess.run(
        [
            sys.executable,
            str(SEED_SWEEP_PATH),
            "--issue",
            "ISSUE-20260309-140",
            "--seed",
            "1337",
            "--seed-start",
            "1",
            "--seed-end",
            "3",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(det_runs), "DAEDALUS_ENFORCE_DETERMINISM": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert det.returncode == 0, det.stdout + det.stderr
    det_meta = _latest_run_json(det_runs)
    det_report = _latest_report(det_runs, "seed_sweep_report.json")
    assert det_meta["seed_contract"] == "per-seed"
    assert det_meta["ambient_root_seed"] is None
    assert [sample["effective_seed"] for sample in det_report["samples"]] == [1, 2, 3]

    amb = subprocess.run(
        [
            sys.executable,
            str(SEED_SWEEP_PATH),
            "--issue",
            "ISSUE-20260309-140",
            "--seed",
            "1337",
            "--seed-start",
            "1",
            "--seed-end",
            "3",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(amb_runs), "DAEDALUS_ENFORCE_DETERMINISM": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert amb.returncode == 0, amb.stdout + amb.stderr
    amb_meta = _latest_run_json(amb_runs)
    amb_report = _latest_report(amb_runs, "seed_sweep_report.json")
    assert amb_meta["seed_contract"] == "ambient-derived"
    assert isinstance(amb_meta["ambient_root_seed"], int)
    effective = [sample["effective_seed"] for sample in amb_report["samples"]]
    assert all(isinstance(seed, int) for seed in effective)
    assert effective != [1, 2, 3]
    assert len(set(effective)) == 3
    assert all(sample["seed_contract"] == "ambient-derived" for sample in amb_report["samples"])
