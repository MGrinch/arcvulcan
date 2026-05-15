from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import GROUNDING_CLOSE, GROUNDING_OPEN, build_tutor_prompt


def _make_repo(root: Path) -> None:
    (root / "STABLE").mkdir(parents=True, exist_ok=True)
    (root / "STABLE" / "ROLE_PROTOCOL.md").write_text("ROLE guidance", encoding="utf-8")
    sources_dir = root / "curriculum" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (root / "curriculum" / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "demo_source",
                        "title": "Demo Source",
                        "path": "sources/demo.md",
                        "tags": ["demo"],
                        "license": "demo",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (sources_dir / "demo.md").write_text("travel speed heat control", encoding="utf-8")


def test_invalid_absolute_grounding_dir_fails_closed_in_meta() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        cfg = XYZGLConfig(
            protocol_reground_every=1,
            grounding_mode="local",
            grounding_dir=str(root / "curriculum"),
            max_chars_in=3_000,
        )

        with patch("xyzgl.prompting._repo_root", return_value=root):
            prompt, meta = build_tutor_prompt("Need help with travel speed", cfg=cfg, turn_index=0)

    assert meta.grounding_enabled is False
    assert meta.grounding_meta == {
        "snippets": [],
        "grounding_dir": str(root / "curriculum"),
        "error": "invalid_grounding_dir",
    }
    assert GROUNDING_OPEN not in prompt
    assert GROUNDING_CLOSE not in prompt



def test_valid_repo_relative_grounding_dir_keeps_grounding_enabled() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        _make_repo(root)
        cfg = XYZGLConfig(
            protocol_reground_every=1,
            grounding_mode="local",
            grounding_dir="curriculum",
            max_chars_in=3_000,
        )

        with patch("xyzgl.prompting._repo_root", return_value=root):
            prompt, meta = build_tutor_prompt("Need help with travel speed", cfg=cfg, turn_index=0)

    assert meta.grounding_enabled is True
    assert GROUNDING_OPEN in prompt
    assert GROUNDING_CLOSE in prompt
