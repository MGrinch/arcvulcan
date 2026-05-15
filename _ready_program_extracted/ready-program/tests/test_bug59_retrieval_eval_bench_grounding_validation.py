from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _load_bench_module():
    spec = importlib.util.spec_from_file_location(
        "retrieval_eval_bench_under_test_bug59", REPO_ROOT / "tools" / "retrieval_eval_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported on this platform")
def test_grounding_dir_symlink_escape_is_rejected(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    outside = tmp_path / "outside_curriculum"
    outside.mkdir()
    escape = fake_repo / "escape_curriculum"
    try:
        escape.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not permitted in this environment: {exc}")

    bench_module = _load_bench_module()
    bench_module._REPO_ROOT = fake_repo

    assert bench_module._resolve_grounding_dir("escape_curriculum") is None


def test_invalid_inputs_do_not_allocate_run_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    bench_module = _load_bench_module()
    bench_module._REPO_ROOT = fake_repo

    monkeypatch.setenv("DAEDALUS_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr(sys, "argv", ["retrieval_eval_bench.py", "--issue", "ISSUE-20260315-059"])

    rc = bench_module.main()
    out = capsys.readouterr().out

    assert rc == 2
    assert "invalid grounding dir" in out
    assert list(runs_dir.iterdir()) == []
