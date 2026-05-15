from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.grounding.prompting import build_grounding


AUDIT_PATH = REPO_ROOT / "tools" / "grounding_injection_audit.py"


def _write_source_cap_corpus(root: Path) -> None:
    sources_dir = root / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    manifest_sources = []
    for idx in range(1, 502):
        rel = f"sources/doc_{idx:03d}.md"
        text = f"generic filler document {idx}\n"
        if idx == 501:
            text = "cap_only_needle retrieval anchor\n"
        (root / rel).write_text(text, encoding="utf-8")
        manifest_sources.append({
            "id": f"doc_{idx:03d}",
            "title": f"Document {idx}",
            "path": rel,
            "tags": [],
            "license": "demo",
        })
    (root / "manifest.json").write_text(json.dumps({"sources": manifest_sources}), encoding="utf-8")


def test_build_grounding_surfaces_source_cap_warning(tmp_path):
    corpus_dir = tmp_path / "curriculum"
    _write_source_cap_corpus(corpus_dir)

    text, meta = build_grounding(corpus_dir, "cap_only_needle", max_snippets=3, max_chars=600)

    assert text == ""
    assert meta["snippets"] == []
    assert "source_limit_exceeded:501>500" in meta["warnings"]
    assert meta["corpus_stats"]["manifest_source_count"] == 501
    assert meta["corpus_stats"]["truncated_source_count"] == 1


def test_grounding_audit_fails_when_source_cap_suppresses_only_match(tmp_path):
    rel_dir = Path("tests_tmp_bug46_corpus")
    corpus_dir = REPO_ROOT / rel_dir
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    try:
        _write_source_cap_corpus(corpus_dir)
        runs_dir = tmp_path / "runs"
        proc = subprocess.run(
            [
                sys.executable,
                str(AUDIT_PATH),
                "--issue",
                "ISSUE-20260309-046",
                "--text",
                "cap_only_needle",
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
        assert "FAIL: wrote outputs to" in proc.stdout
        report_paths = sorted(runs_dir.glob("*/grounding_audit_report.json"))
        assert report_paths
        report = json.loads(report_paths[-1].read_text(encoding="utf-8"))
        assert report["pass"] is False
        assert "grounding requested but no snippets were produced" in report["problems"]
        assert "corpus warning: source_limit_exceeded:501>500" in report["problems"]
    finally:
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
