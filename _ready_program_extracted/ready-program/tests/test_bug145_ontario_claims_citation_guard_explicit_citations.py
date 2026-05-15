from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "ISSUE-20260318-145"


def _latest_run_dir(root: Path) -> Path:
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime_ns)
    assert runs, "expected ontario_claims_citation_guard to create a run bundle"
    return runs[-1]


def test_explicit_citation_without_grounding_is_not_a_false_fail(tmp_path: Path) -> None:
    report_path = tmp_path / "turn_report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "turn_report@1",
                "reply": "Ontario requirement summary [src:manual:1]",
                "prompt_meta": {"grounding": {"snippets": []}},
            }
        ),
        encoding="utf-8",
    )

    run_root = tmp_path / "runs"
    env = dict(os.environ)
    env["DAEDALUS_RUNS_DIR"] = str(run_root)

    proc = subprocess.run(
        [
            sys.executable,
            "tools/ontario_claims_citation_guard.py",
            "--issue",
            ISSUE_ID,
            "--enforce",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    run_dir = _latest_run_dir(run_root)
    report = json.loads((run_dir / "ontario_claims_report.json").read_text(encoding="utf-8"))
    assert len(report["findings"]) == 1
    finding = report["findings"][0]
    assert finding["severity"] == "WARN"
    assert finding["has_grounding"] is False
    assert finding["has_citations"] is True
    assert finding["citation_count"] == 1
    assert finding["valid_citation_count"] == 0
    assert finding["invalid_citation_count"] == 1
