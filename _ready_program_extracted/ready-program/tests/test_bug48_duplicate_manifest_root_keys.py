from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.grounding.prompting import _CORPUS_CACHE, build_grounding


AUDIT_PATH = REPO_ROOT / "tools" / "grounding_injection_audit.py"
DUPLICATE_WARNING = "manifest_parse_error:duplicate key: 'sources'"


def _write_duplicate_sources_manifest(root: Path) -> None:
    sources_dir = root / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "good.md").write_text("needle48 answer anchor\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        """
{
  "sources": [
    {
      "id": "good",
      "title": "Good Source",
      "path": "sources/good.md",
      "tags": [],
      "license": "demo"
    }
  ],
  "sources": []
}
""".strip()
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _clear_grounding_cache():
    _CORPUS_CACHE.clear()
    yield
    _CORPUS_CACHE.clear()


def test_build_grounding_surfaces_duplicate_root_key_manifest_error(tmp_path):
    corpus_dir = tmp_path / "curriculum"
    _write_duplicate_sources_manifest(corpus_dir)

    text, meta = build_grounding(corpus_dir, "needle48", max_snippets=3, max_chars=600)

    assert text == ""
    assert meta["snippets"] == []
    assert DUPLICATE_WARNING in meta["warnings"]
    assert meta["corpus_stats"]["manifest_error"] == "manifest_parse_error"
    assert meta["corpus_stats"]["manifest_error_detail"] == "duplicate key: 'sources'"


def test_grounding_audit_fails_on_duplicate_root_key_manifest(tmp_path):
    rel_dir = Path("tests_tmp_bug48_corpus")
    corpus_dir = REPO_ROOT / rel_dir
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    try:
        _write_duplicate_sources_manifest(corpus_dir)
        runs_dir = tmp_path / "runs"
        proc = subprocess.run(
            [
                sys.executable,
                str(AUDIT_PATH),
                "--issue",
                "ISSUE-20260309-048",
                "--text",
                "needle48",
            ],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "DAEDALUS_RUNS_DIR": str(runs_dir),
                "DAEDALUS_GROUNDING_DIR": str(rel_dir).replace("\\", "/"),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        report_paths = sorted(runs_dir.glob("*/grounding_audit_report.json"))
        assert report_paths
        report = json.loads(report_paths[-1].read_text(encoding="utf-8"))
        assert report["pass"] is False
        assert "grounding requested but no snippets were produced" in report["problems"]
        assert f"corpus warning: {DUPLICATE_WARNING}" in report["problems"]
    finally:
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
