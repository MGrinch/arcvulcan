from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import GROUNDING_OPEN, build_tutor_prompt


class Bug20PromptingGroundingEnablementTests(unittest.TestCase):
    def _make_repo(self, root: Path) -> None:
        (root / "STABLE").mkdir(parents=True, exist_ok=True)
        (root / "STABLE" / "ROLE_PROTOCOL.md").write_text("ROLE guidance", encoding="utf-8")
        sources_dir = root / "curriculum" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
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
        (root / "curriculum" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (sources_dir / "demo.md").write_text("travel speed heat control", encoding="utf-8")

    def test_invalid_absolute_grounding_dir_disables_grounding_meta(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo(root)
            cfg = XYZGLConfig(
                protocol_reground_every=1,
                grounding_mode="local",
                grounding_dir=str(root / "curriculum"),
                max_chars_in=3_000,
            )

            with patch("xyzgl.prompting._repo_root", return_value=root):
                prompt, meta = build_tutor_prompt("Need help with travel speed", cfg=cfg, turn_index=0)

        self.assertFalse(meta.grounding_enabled)
        self.assertEqual(meta.grounding_meta.get("error"), "invalid_grounding_dir")
        self.assertNotIn(GROUNDING_OPEN, prompt)

    def test_valid_repo_relative_grounding_dir_keeps_grounding_enabled(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo(root)
            cfg = XYZGLConfig(
                protocol_reground_every=1,
                grounding_mode="local",
                grounding_dir="curriculum",
                max_chars_in=3_000,
            )

            with patch("xyzgl.prompting._repo_root", return_value=root):
                prompt, meta = build_tutor_prompt("Need help with travel speed", cfg=cfg, turn_index=0)

        self.assertTrue(meta.grounding_enabled)
        self.assertIn(GROUNDING_OPEN, prompt)


if __name__ == "__main__":
    unittest.main()
