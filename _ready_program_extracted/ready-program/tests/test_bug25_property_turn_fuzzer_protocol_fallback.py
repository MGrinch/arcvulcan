from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_property_turn_fuzzer_fails_on_protocol_fallback_and_keeps_testcase() -> None:
    runs_dir = REPO_ROOT / "tmp_test_bug25_runs"
    if runs_dir.exists():
        for child in runs_dir.iterdir():
            if child.is_dir():
                for nested in child.rglob('*'):
                    if nested.is_file():
                        nested.unlink()
                for nested in sorted(child.rglob('*'), reverse=True):
                    if nested.is_dir():
                        nested.rmdir()
                child.rmdir()
            else:
                child.unlink()
    else:
        runs_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "DAEDALUS_RUNS_DIR": str(runs_dir),
            "DAEDALUS_PROTOCOL_PATH": "missing/does_not_exist.md",
        }
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "property_turn_fuzzer.py"),
            "--issue",
            "BUG-25",
            "--cases",
            "1",
            "--max-len",
            "24",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr

    run_dirs = sorted(p for p in runs_dir.iterdir() if p.is_dir())
    assert run_dirs
    report = json.loads((run_dirs[-1] / "property_fuzz_report.json").read_text(encoding="utf-8"))

    assert report["overall"] == "FAIL"
    assert report["problems"]

    row = report["results"][0]
    assert row["pass"] is False
    assert row["testcase_text"]
    assert row["testcase_hash"]
    assert row["prompt_meta"]["protocol_loaded"] is False
    assert row["prompt_meta"]["protocol_fallback"] is True
    assert row["prompt_meta"]["protocol_load_error"] == "protocol_load_error: missing_or_not_file"
    assert any(problem == "prompt_meta.protocol_loaded is false" for problem in row["problems"])
    assert any(problem == "prompt_meta.protocol_fallback is true" for problem in row["problems"])
    assert any(problem == "unexpected prompt_meta.protocol_load_error" for problem in row["problems"])
    assert any("prompt_meta.protocol_fallback is true" in problem for problem in report["problems"])
