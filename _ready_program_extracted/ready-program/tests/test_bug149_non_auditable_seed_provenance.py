from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260318-149"


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)


def _latest_run_dir(run_root: Path) -> Path:
    run_dirs = sorted((p for p in run_root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    assert run_dirs, "expected tool to create a run bundle"
    return run_dirs[-1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("tool_rel", "extra_args", "report_name"),
    [
        ("tools/doc_code_link_checker.py", [], "doc_link_report.json"),
        ("tools/mutation_suite.py", ["--engine", "builtin", "--target", "xyzgl", "--dry-run"], "mutation_report.json"),
    ],
)
def test_bug149_tools_do_not_claim_noncontract_seed_provenance(
    tmp_path: Path, tool_rel: str, extra_args: list[str], report_name: str
) -> None:
    run_root = tmp_path / "runs"
    run_root.mkdir()
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    result = _run([sys.executable, tool_rel, "--issue", ISSUE_ID, *extra_args], env=env)
    assert result.returncode in {0, 1}, result.stdout + result.stderr

    run_dir = _latest_run_dir(run_root)
    run_meta = _load_json(run_dir / "run.json")
    report = _load_json(run_dir / report_name)

    assert "seed" not in run_meta
    assert "seed" not in report
