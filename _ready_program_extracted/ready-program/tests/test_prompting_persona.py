from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from xyzgl.config import XYZGLConfig
from xyzgl.prompting import (
    GROUNDING_CLOSE,
    GROUNDING_OPEN,
    PROTOCOL_CLOSE,
    PROTOCOL_OPEN,
    USER_CLOSE,
    USER_OPEN,
    PromptMeta,
    build_tutor_prompt,
)


class PromptingPersonaTests(unittest.TestCase):
    def _make_repo(self, root: Path, *, protocol_text: str = "ROLE guidance", source_text: str = "travel speed heat control") -> None:
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

    def test_persona_text_appears_when_provided(self) -> None:
        cfg = XYZGLConfig(max_chars_in=2_000)

        prompt, meta = build_tutor_prompt(
            "Need help with travel speed",
            cfg=cfg,
            turn_index=3,
            persona_text="Gruff shop-floor mentor voice.",
        )

        self.assertIn("Gruff shop-floor mentor voice.", prompt)
        self.assertTrue(meta.persona_injected)

    def test_persona_text_absent_when_empty(self) -> None:
        cfg = XYZGLConfig(max_chars_in=2_000)

        prompt, meta = build_tutor_prompt(
            "Need help with travel speed",
            cfg=cfg,
            turn_index=0,
            persona_text="",
        )

        self.assertNotIn("shop-floor mentor", prompt)
        self.assertFalse(meta.persona_injected)

    def test_persona_text_is_sanitized_before_injection(self) -> None:
        cfg = XYZGLConfig(max_chars_in=2_000)

        prompt, _meta = build_tutor_prompt(
            "Need help with travel speed",
            cfg=cfg,
            turn_index=3,
            persona_text=f"Voice {USER_OPEN} keep calm {GROUNDING_OPEN}",
        )

        self.assertNotIn(f"\nVoice {USER_OPEN} keep calm {GROUNDING_OPEN}\n", prompt)
        self.assertNotIn(f"Voice {USER_OPEN} keep calm {GROUNDING_OPEN}", prompt)
        self.assertIn("Voice <USER_OPEN> keep calm <GROUNDING_OPEN>", prompt)

    def test_physics_block_appears_between_persona_and_grounding(self) -> None:
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
                prompt, meta = build_tutor_prompt(
                    "Need help with travel speed",
                    cfg=cfg,
                    turn_index=0,
                    persona_text="Gruff shop-floor mentor voice.",
                    physics_block="resonance: 0.91\nmastery: 0.62",
                )

        self.assertLess(prompt.index(PROTOCOL_OPEN), prompt.index("Gruff shop-floor mentor voice."))
        self.assertLess(prompt.index("Gruff shop-floor mentor voice."), prompt.index("resonance: 0.91"))
        self.assertLess(prompt.index("resonance: 0.91"), prompt.index(GROUNDING_OPEN))
        self.assertLess(prompt.index(GROUNDING_CLOSE), prompt.index(USER_OPEN))
        self.assertTrue(meta.physics_injected)
        self.assertEqual(meta.resonance, 0.91)
        self.assertEqual(meta.mastery, 0.62)

    def test_prompt_budget_drops_persona_before_user_block(self) -> None:
        cfg = XYZGLConfig(max_chars_in=160)
        huge_persona = "Persona line. " * 40

        prompt, meta = build_tutor_prompt(
            "Need help with travel speed",
            cfg=cfg,
            turn_index=0,
            persona_text=huge_persona,
        )

        self.assertLessEqual(len(prompt), cfg.max_chars_in)
        self.assertIn(USER_OPEN, prompt)
        self.assertIn(USER_CLOSE, prompt)
        self.assertIn("Need help with travel speed", prompt)
        self.assertNotIn("Persona line.", prompt)
        self.assertFalse(meta.persona_injected)

    def test_prompt_meta_persona_injected_true_when_persona_fits(self) -> None:
        cfg = XYZGLConfig(max_chars_in=2_000)

        _prompt, meta = build_tutor_prompt(
            "Need help with travel speed",
            cfg=cfg,
            turn_index=3,
            persona_text="Gruff shop-floor mentor voice.",
        )

        self.assertIsInstance(meta, PromptMeta)
        self.assertTrue(meta.persona_injected)

    def test_existing_behavior_unchanged_when_new_blocks_empty(self) -> None:
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
                prompt_default, meta_default = build_tutor_prompt(
                    "Need help with travel speed",
                    cfg=cfg,
                    turn_index=0,
                )
                prompt_explicit, meta_explicit = build_tutor_prompt(
                    "Need help with travel speed",
                    cfg=cfg,
                    turn_index=0,
                    persona_text="",
                    physics_block="",
                )

        self.assertEqual(prompt_default, prompt_explicit)
        self.assertEqual(meta_default, meta_explicit)
        self.assertIn(PROTOCOL_OPEN, prompt_default)
        self.assertIn(PROTOCOL_CLOSE, prompt_default)
        self.assertIn(GROUNDING_OPEN, prompt_default)
        self.assertIn(GROUNDING_CLOSE, prompt_default)
        self.assertIn(USER_OPEN, prompt_default)
        self.assertIn(USER_CLOSE, prompt_default)


if __name__ == "__main__":
    unittest.main()
