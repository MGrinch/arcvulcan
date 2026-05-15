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

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import build_tutor_prompt


AUDIT_PATH = REPO_ROOT / "tools" / "grounding_injection_audit.py"


def _write_bug88_corpus(root: Path) -> None:
    sources_dir = root / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "doc.md").write_text(
        "tail_only_anchor late_cap_token\n",
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "bug88",
                        "title": "Bug 88 Corpus",
                        "path": "sources/doc.md",
                        "tags": [],
                        "license": "demo",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_build_tutor_prompt_grounds_on_effective_capped_query(tmp_path):
    rel_dir = Path("tests_tmp_bug88_prompt")
    corpus_dir = REPO_ROOT / rel_dir
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    try:
        _write_bug88_corpus(corpus_dir)
        cfg = XYZGLConfig(
            grounding_mode="local",
            grounding_dir=str(rel_dir).replace("\\", "/"),
            max_chars_in=32,
            grounding_max_snippets=3,
            grounding_max_chars=400,
        )
        raw_query = ("x" * 40) + " late_cap_token"

        prompt, meta = build_tutor_prompt(raw_query, cfg=cfg, turn_index=0)

        assert meta.grounding_enabled is True
        assert meta.grounding_meta is not None
        assert meta.grounding_meta["snippets"] == []
        assert "late_cap_token" not in prompt
        assert meta.user_block_text == "x" * 32
    finally:
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)


def test_grounding_audit_uses_same_capped_query_as_runtime(tmp_path):
    rel_dir = Path("tests_tmp_bug88_audit")
    corpus_dir = REPO_ROOT / rel_dir
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    try:
        _write_bug88_corpus(corpus_dir)
        runs_dir = tmp_path / "runs"
        raw_query = ("x" * 40) + " late_cap_token"
        proc = subprocess.run(
            [
                sys.executable,
                str(AUDIT_PATH),
                "--issue",
                "ISSUE-20260315-088",
                "--text",
                raw_query,
            ],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(REPO_ROOT),
                "DAEDALUS_RUNS_DIR": str(runs_dir),
                "DAEDALUS_GROUNDING_DIR": str(rel_dir).replace("\\", "/"),
                "DAEDALUS_MAX_CHARS_IN": "32",
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
        assert report["effective_query"] == "x" * 32
        assert "grounding requested but no snippets were produced" in report["problems"]
    finally:
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
