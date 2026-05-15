import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "secret_scanner.py"
ISSUE = "ISSUE-20260318-143"
TOKEN = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"


def _run_scan(scan_root: Path, runs_dir: Path) -> subprocess.CompletedProcess[str]:
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


def test_example_and_fixture_path_context_suppresses_placeholder_hits(tmp_path):
    scan_root = tmp_path / "scan-root"
    example_dir = scan_root / "docs" / "examples"
    fixture_dir = scan_root / "tests" / "fixtures"
    example_dir.mkdir(parents=True)
    fixture_dir.mkdir(parents=True)

    (example_dir / "openai.env").write_text(f"OPENAI_API_KEY={TOKEN}\n", encoding="utf-8")
    (fixture_dir / "aws.env").write_text("AWS_ACCESS_KEY_ID=AKIA0123456789ABCDEF\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    proc = _run_scan(scan_root, runs_dir)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _load_report(runs_dir)
    assert report["overall"] == "PASS"
    assert report["hit_count"] == 0
    assert report["hits"] == []


def test_non_placeholder_paths_still_report_live_secrets(tmp_path):
    scan_root = tmp_path / "scan-root"
    prod_dir = scan_root / "config" / "prod"
    prod_dir.mkdir(parents=True)
    (prod_dir / "secrets.env").write_text(f"OPENAI_API_KEY={TOKEN}\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    proc = _run_scan(scan_root, runs_dir)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _load_report(runs_dir)
    assert report["overall"] == "FAIL"
    assert report["hit_count"] == 1
    assert report["hits"][0]["file"] == "config/prod/secrets.env"
    assert {hit["pattern"] for hit in report["hits"][0]["hits"]} == {"openai_api_key", "assignment_secret"}
