from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import GROUNDING_CLOSE, GROUNDING_OPEN, build_tutor_prompt

REDTEAM_PATH = REPO_ROOT / "tools" / "redteam_rag_poisoning_suite.py"


def _load_redteam_module():
    tools_dir = str(REDTEAM_PATH.parent)
    added = False
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
        added = True
    try:
        spec = importlib.util.spec_from_file_location("redteam_rag_poisoning_suite", REDTEAM_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if added and sys.path[:1] == [tools_dir]:
            sys.path.pop(0)
def test_build_tutor_prompt_disables_grounding_meta_for_invalid_absolute_grounding_dir() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        (root / "STABLE").mkdir(parents=True, exist_ok=True)
        (root / "STABLE" / "ROLE_PROTOCOL.md").write_text("role protocol", encoding="utf-8")

        bad_grounding_dir = root / "external_curriculum"
        bad_grounding_dir.mkdir(parents=True, exist_ok=True)

        cfg = XYZGLConfig(
            protocol_reground_every=1,
            grounding_mode="local",
            grounding_dir=str(bad_grounding_dir),
        )

        with patch("xyzgl.prompting._repo_root", return_value=root):
            prompt, meta = build_tutor_prompt("Explain 2F vs 1F.", cfg=cfg, turn_index=0)

        assert GROUNDING_OPEN not in prompt
        assert GROUNDING_CLOSE not in prompt
        assert meta.grounding_enabled is False
        assert meta.grounding_meta == {
            "snippets": [],
            "grounding_dir": str(bad_grounding_dir),
            "error": "invalid_grounding_dir",
        }


def test_redteam_boundary_check_requires_protocol_and_grounding_markers() -> None:
    mod = _load_redteam_module()

    problems = mod._check_boundaries(f"<<<USER>>>\nhello\n<<<END_USER>>>")

    assert "missing protocol markers" in problems
    assert "missing grounding markers" in problems


def test_redteam_rag_poisoning_suite_builds_real_grounding_and_passes(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    proc = subprocess.run(
        [
            sys.executable,
            str(REDTEAM_PATH),
            "--issue",
            "ISSUE-20260314-020",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DAEDALUS_RUNS_DIR": str(runs_dir),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS: wrote outputs to" in proc.stdout
    report_paths = sorted(runs_dir.glob("*/redteam_rag_poison_report.json"))
    assert report_paths
    report = json.loads(report_paths[-1].read_text(encoding="utf-8"))
    assert report["overall"] == "PASS"
    assert report["cases"][0]["pass"] is True
    assert report["cases"][0]["problems"] == []
