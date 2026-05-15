import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "secret_scanner.py"
ISSUE = "ISSUE-20260315-106"


def test_literal_only_files_and_sk_proj_keys_are_scanned(tmp_path):
    scan_root = tmp_path / "scan-root"
    scan_root.mkdir()
    (scan_root / "google.txt").write_text(
        "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q\n",
        encoding="utf-8",
    )
    (scan_root / "openai.txt").write_text(
        "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789\n",
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
    assert report["hit_count"] == 2

    by_file = {entry["file"]: {hit["pattern"] for hit in entry["hits"]} for entry in report["hits"]}
    assert by_file["google.txt"] == {"google_api_key"}
    assert by_file["openai.txt"] == {"openai_api_key"}
