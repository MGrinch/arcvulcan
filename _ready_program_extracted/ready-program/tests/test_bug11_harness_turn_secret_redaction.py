from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HARNESS_PATH = REPO_ROOT / "tools" / "harness_turn.py"


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    assert candidates, "expected at least one harness_turn run directory"
    return candidates[-1]


def test_harness_turn_redacts_modern_secret_families_from_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    secret_payload = "\n".join(
        [
            "github_pat_abcdEFGHijklMNOPqrstUVWXyz0123456789",
            "ghs_abcdEFGHijklMNOPqrstUVWXyz0123456789",
            "glpat-ABCD-efgh-ijkl-mnop-qrst-uvwx-1234567890",
            "sk_live_abcdEFGH-ijklMNOP-qrstUVWX-1234567890",
            "npm_abcdEFGH-ijklMNOP-qrstUVWX-1234567890",
            "xoxs-123456789012-abcdefghijklmnopQRSTUVWX",
            "hf_abcdEFGHijklMNOPqrstUVWXyz0123456789",
            "sk-ant-api03-abcdefghijklmnopQRSTUVWXyz0123456789",
            "xapp-1-abcdefghijklmnopQRSTUVWX-1234567890",
            "ya29.a0AfH6SMBabcdefghijklmnopQRSTUVWXyz0123456789",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAlwAAAAdzc2gtcnNh",
            "-----END OPENSSH PRIVATE KEY-----",
        ]
    )

    proc = subprocess.run(
        [sys.executable, str(HARNESS_PATH), "--issue", "ISSUE-20260314-011", "--text", secret_payload],
        cwd=REPO_ROOT,
        env={**os.environ, "DAEDALUS_RUNS_DIR": str(runs_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    run_dir = _latest_run_dir(runs_dir)
    report_text = (run_dir / "turn_report.json").read_text(encoding="utf-8")
    summary_text = (run_dir / "turn_summary.md").read_text(encoding="utf-8")
    report = json.loads(report_text)
    turn_result = report["payload"]["turn_result"]

    for forbidden in [
        "github_pat_abcdEFGHijklMNOPqrstUVWXyz0123456789",
        "ghs_abcdEFGHijklMNOPqrstUVWXyz0123456789",
        "glpat-ABCD-efgh-ijkl-mnop-qrst-uvwx-1234567890",
        "sk_live_abcdEFGH-ijklMNOP-qrstUVWX-1234567890",
        "npm_abcdEFGH-ijklMNOP-qrstUVWX-1234567890",
        "xoxs-123456789012-abcdefghijklmnopQRSTUVWX",
        "hf_abcdEFGHijklMNOPqrstUVWXyz0123456789",
        "sk-ant-api03-abcdefghijklmnopQRSTUVWXyz0123456789",
        "xapp-1-abcdefghijklmnopQRSTUVWX-1234567890",
        "ya29.a0AfH6SMBabcdefghijklmnopQRSTUVWXyz0123456789",
        "BEGIN OPENSSH PRIVATE KEY",
        "END OPENSSH PRIVATE KEY",
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAlwAAAAdzc2gtcnNh",
    ]:
        assert forbidden not in report_text
        assert forbidden not in summary_text

    assert turn_result["input"] == "<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted>\n<redacted-private-key>"
    assert turn_result["input_raw"] == turn_result["input"]
    assert turn_result["input_routed"] == turn_result["input"]
    assert turn_result["prompt_user_block"] == turn_result["input"]
    assert turn_result["prompt_meta"]["user_block_text"] == turn_result["input"]
    assert "<redacted-private-key>" in report_text
    assert "<redacted-private-key>" in summary_text
