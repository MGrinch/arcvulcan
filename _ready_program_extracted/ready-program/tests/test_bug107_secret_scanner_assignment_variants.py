import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "secret_scanner.py"
ISSUE = "ISSUE-20260319-107"


def test_assignment_variants_cover_bearer_generic_and_unquoted_password(tmp_path):
    scan_root = tmp_path / "scan-root"
    scan_root.mkdir()
    (scan_root / "sample.env").write_text(
        "authorization=Bearer ABCD/EFGH+IJKL.MNOPQRST\n"
        "api_key=ABCD/EFGH+IJKL.MNOPQRST\n"
        "secret=AAAA.BBBB.CCCC.DDDD\n"
        "password=supersecret12345\n",
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs"
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(runs_dir)

    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--issue",
            ISSUE,
            "--path",
            str(scan_root),
            "--allow-external-path",
            "--enforce",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert proc.returncode == 1, proc.stdout + proc.stderr
    report_paths = sorted(runs_dir.glob("*/secret_scan_report.json"))
    assert len(report_paths) == 1, report_paths
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))

    assert report["overall"] == "FAIL"
    assert report["hit_count"] == 1

    hits = report["hits"][0]["hits"]
    assert len(hits) == 4
    patterns = [hit["pattern"] for hit in hits]
    assert patterns.count("assignment_secret") == 3
    assert "bearer_literal" in patterns
