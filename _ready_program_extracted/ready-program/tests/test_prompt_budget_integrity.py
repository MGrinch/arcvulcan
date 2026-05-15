from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xyzgl.backends.stub import _extract_user
from xyzgl.config import XYZGLConfig
from xyzgl.prompting import (
    GROUNDING_CLOSE,
    GROUNDING_OPEN,
    PROTOCOL_CLOSE,
    PROTOCOL_OPEN,
    USER_CLOSE,
    USER_OPEN,
    build_tutor_prompt,
)


class PromptBudgetIntegrityTests(unittest.TestCase):
    def _make_repo(self, root: Path, *, protocol_text: str, source_text: str) -> None:
        (root / "STABLE").mkdir(parents=True, exist_ok=True)
        (root / "STABLE" / "ROLE_PROTOCOL.md").write_text(protocol_text, encoding="utf-8")

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
        (sources_dir / "demo.md").write_text(source_text, encoding="utf-8")

    def test_budgeted_prompt_keeps_user_block_and_closes_optional_markers(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            self._make_repo(
                root,
                protocol_text="ROLE " * 100,
                source_text="travel speed heat control arc length electrode angle " * 200,
            )
            cfg = XYZGLConfig(
                protocol_reground_every=1,
                grounding_mode="local",
                grounding_dir="curriculum",
                grounding_max_chars=10_000,
                max_chars_in=1_100,
            )

            with patch("xyzgl.prompting._repo_root", return_value=root):
                prompt, _meta = build_tutor_prompt("Need help with travel speed and heat control", cfg=cfg, turn_index=0)

            self.assertLessEqual(len(prompt), cfg.max_chars_in)
            self.assertIn(USER_OPEN, prompt)
            self.assertIn(USER_CLOSE, prompt)
            self.assertIn(PROTOCOL_OPEN, prompt)
            self.assertIn(PROTOCOL_CLOSE, prompt)
            self.assertIn(GROUNDING_OPEN, prompt)
            self.assertIn(GROUNDING_CLOSE, prompt)
            self.assertLess(prompt.index(PROTOCOL_OPEN), prompt.index(PROTOCOL_CLOSE))
            self.assertLess(prompt.index(GROUNDING_OPEN), prompt.index(GROUNDING_CLOSE))
            self.assertLess(prompt.index(GROUNDING_CLOSE), prompt.index(USER_OPEN))
            self.assertIn("Need help with travel speed", _extract_user(prompt))

    def test_marker_heavy_user_text_still_preserves_closed_user_block(self) -> None:
        cfg = XYZGLConfig(max_chars_in=95)
        user_text = USER_OPEN * 20

        prompt, _meta = build_tutor_prompt(user_text, cfg=cfg, turn_index=3)

        self.assertLessEqual(len(prompt), cfg.max_chars_in)
        self.assertIn(USER_OPEN, prompt)
        self.assertIn(USER_CLOSE, prompt)
        extracted = _extract_user(prompt)
        self.assertTrue(extracted)
        self.assertNotIn(USER_OPEN, extracted)
        self.assertNotIn(USER_CLOSE, extracted)
        self.assertIn("<USER_OPEN>", extracted)


if __name__ == "__main__":
    unittest.main()
