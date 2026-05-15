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

from xyzgl.grounding.corpus import MAX_MANIFEST_BYTES, load_corpus
from xyzgl.grounding.prompting import build_grounding


AUDIT_PATH = REPO_ROOT / "tools" / "grounding_injection_audit.py"


def _write_oversized_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    header = '{"sources":['
    footer = ']}'
    filler = '{},'
    repeats = ((MAX_MANIFEST_BYTES - len(header) - len(footer)) // len(filler)) + 8
    manifest = header + (filler * repeats) + '{}'+ footer
    assert len(manifest.encode("utf-8")) > MAX_MANIFEST_BYTES
    (root / "manifest.json").write_text(manifest, encoding="utf-8")


def test_load_corpus_surfaces_manifest_too_large_error(tmp_path):
    corpus_dir = tmp_path / "curriculum"
    _write_oversized_manifest(corpus_dir)

    corpus = load_corpus(corpus_dir)

    assert corpus.sources == []
    assert corpus.passages == []
    assert corpus.stats["manifest_error"] == "manifest_too_large"
    detail = corpus.stats["manifest_error_detail"]
    assert detail.endswith(f">{MAX_MANIFEST_BYTES}")
    assert f"manifest_too_large:{detail}" in corpus.warnings


def test_build_grounding_and_audit_report_manifest_too_large(tmp_path):
    rel_dir = Path("tests_tmp_bug69_corpus")
    corpus_dir = REPO_ROOT / rel_dir
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    try:
        _write_oversized_manifest(corpus_dir)

        text, meta = build_grounding(corpus_dir, "oversize probe", max_snippets=3, max_chars=600)
        assert text == ""
        assert meta["snippets"] == []
        assert meta["corpus_stats"]["manifest_error"] == "manifest_too_large"
        warning = next(w for w in meta["warnings"] if w.startswith("manifest_too_large:"))

        runs_dir = tmp_path / "runs"
        proc = subprocess.run(
            [
                sys.executable,
                str(AUDIT_PATH),
                "--issue",
                "ISSUE-20260319-069",
                "--text",
                "oversize probe",
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
        assert f"corpus warning: {warning}" in report["problems"]
    finally:
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
