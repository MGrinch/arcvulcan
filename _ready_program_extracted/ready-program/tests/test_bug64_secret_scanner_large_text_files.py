import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "secret_scanner.py"
ISSUE = "ISSUE-20260320-064"


def _run_scan(scan_root: Path, runs_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DAEDALUS_RUNS_DIR"] = str(runs_dir)
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--issue",
            ISSUE,
            "--path",
            str(scan_root),
            "--allow-external-path",
            "--enforce",
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def _load_report(runs_dir: Path) -> dict:
    report_paths = sorted(runs_dir.glob("*/secret_scan_report.json"))
    assert len(report_paths) == 1, report_paths
    return json.loads(report_paths[0].read_text(encoding="utf-8"))


def test_large_text_files_are_still_scanned_for_secrets(tmp_path: Path) -> None:
    scan_root = tmp_path / "scan-root"
    scan_root.mkdir()
    large_file = scan_root / "large.env"
    large_file.write_text(
        ("A" * 2_050_000) + "\nOPENAI_API_KEY=sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789\n",
        encoding="utf-8",
    )

    runs_dir = tmp_path / "runs"
    proc = _run_scan(scan_root, runs_dir, "--max-bytes", "4000000")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _load_report(runs_dir)
    assert report["overall"] == "FAIL"
    assert report["hit_count"] == 1
    assert report["hits"][0]["file"] == "large.env"
    assert {hit["pattern"] for hit in report["hits"][0]["hits"]} == {"openai_api_key", "assignment_secret"}
    assert report["partial_scan_files"] == []


def test_large_text_budget_truncation_is_reported_instead_of_silent_pass(tmp_path: Path) -> None:
    scan_root = tmp_path / "scan-root"
    scan_root.mkdir()
    large_file = scan_root / "oversized.log"
    large_file.write_text(("B" * 2_250_000) + "\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    proc = _run_scan(scan_root, runs_dir, "--max-bytes", "1024")

    assert proc.returncode == 2, proc.stdout + proc.stderr
    report = _load_report(runs_dir)
    assert report["overall"] == "INCOMPLETE"
    assert report["hit_count"] == 0
    assert report["truncated_reason"] == "max bytes reached (1024)"
    assert report["partial_scan_files"] == [
        {
            "file": "oversized.log",
            "file_size": large_file.stat().st_size,
            "scanned_bytes": 1024,
            "reason": "max bytes reached (1024)",
        }
    ]
