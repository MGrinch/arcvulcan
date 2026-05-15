from __future__ import annotations

from types import SimpleNamespace
import unittest

from xyzgl.persona import PersonaConfig, build_persona_instruction, persona_from_config


class PersonaTests(unittest.TestCase):
    def test_high_resonance_selects_high_behavior(self) -> None:
        cfg = PersonaConfig(
            high_res_behavior="Give a nod.",
            mid_res_behavior="Point out what is missing.",
            low_res_behavior="Be blunt.",
            max_voice_words=12,
        )

        text = build_persona_instruction(cfg, mastery=0.6, resonance=0.87)

        self.assertIn("PERSONA: Miller (Gruff Welding Foreman)", text)
        self.assertIn("Physics: Mastery=0.60, Resonance=0.87", text)
        self.assertIn("Resonance is high", text)
        self.assertIn("Give a nod.", text)
        self.assertIn("under 12 words", text)

    def test_mid_resonance_selects_mid_behavior(self) -> None:
        cfg = PersonaConfig(
            high_res_behavior="high",
            mid_res_behavior="Explain the missing step.",
            low_res_behavior="low",
        )

        text = build_persona_instruction(cfg, mastery=0.25, resonance=0.50)

        self.assertIn("Resonance is mid-range", text)
        self.assertIn("Explain the missing step.", text)
        self.assertNotIn("Resonance is high", text)
        self.assertNotIn("Resonance is low", text)

    def test_low_resonance_selects_low_behavior(self) -> None:
        cfg = PersonaConfig(
            high_res_behavior="high",
            mid_res_behavior="mid",
            low_res_behavior="Call out the mistake directly.",
        )

        text = build_persona_instruction(cfg, mastery=0.9, resonance=0.10)

        self.assertIn("Resonance is low", text)
        self.assertIn("Call out the mistake directly.", text)
        self.assertNotIn("Resonance is high", text)
        self.assertNotIn("Resonance is mid-range", text)

    def test_disabled_persona_returns_none(self) -> None:
        cfg = SimpleNamespace(persona_enabled=False)

        self.assertIsNone(persona_from_config(cfg))

    def test_custom_config_overrides_defaults(self) -> None:
        runtime_cfg = SimpleNamespace(
            persona_enabled=True,
            persona_name="Inspector",
            persona_role="Patient CWB Instructor",
            persona_high_res_behavior="Stay calm and confirm the correct read.",
            persona_mid_res_behavior="Name the gap and point to the next fix.",
            persona_low_res_behavior="Stop the drift and correct it now.",
            persona_max_words=9,
            persona_res_high_threshold=0.91,
            persona_res_low_threshold=0.22,
        )

        persona_cfg = persona_from_config(runtime_cfg)

        self.assertIsNotNone(persona_cfg)
        assert persona_cfg is not None
        self.assertEqual(persona_cfg.name, "Inspector")
        self.assertEqual(persona_cfg.role, "Patient CWB Instructor")
        self.assertEqual(persona_cfg.max_voice_words, 9)
        self.assertEqual(persona_cfg.res_high_threshold, 0.91)
        self.assertEqual(persona_cfg.res_low_threshold, 0.22)

        text = build_persona_instruction(persona_cfg, mastery=0.4, resonance=0.95)
        self.assertIn("PERSONA: Inspector (Patient CWB Instructor)", text)
        self.assertIn("Stay calm and confirm the correct read.", text)
        self.assertIn("under 9 words", text)

    def test_output_is_plain_string_without_structured_markers(self) -> None:
        text = build_persona_instruction(PersonaConfig(), mastery=0.6, resonance=0.6)

        self.assertIsInstance(text, str)
        self.assertNotIn("<<<", text)
        self.assertNotIn(">>>", text)
        self.assertNotIn("```", text)
        self.assertTrue(text.startswith("PERSONA: "))


if __name__ == "__main__":
    unittest.main()
