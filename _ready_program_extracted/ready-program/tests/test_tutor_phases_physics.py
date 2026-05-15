from __future__ import annotations

import unittest
from unittest.mock import patch

from xyzgl.backends.base import BackendResult
from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.policies import TeachingBudget
from xyzgl.orchestrator.phases import TeachPhase
from xyzgl.orchestrator.tutor_phases import run_eval_phase, run_teach_phase
from xyzgl.prompting import PromptMeta


class _RecordingBackend:
    name = "stub"

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        self.prompts.append(prompt)
        return BackendResult(text=self.text, backend="stub", model="stub", latency_ms=1)


def _prompt_meta() -> PromptMeta:
    return PromptMeta(
        protocol_regrounded=False,
        protocol_path="STABLE/ROLE_PROTOCOL.md",
        grounding_enabled=False,
        grounding_meta={},
    )


class TutorPhasesPhysicsTests(unittest.TestCase):
    def test_run_eval_phase_with_physics_records_prompt_meta(self) -> None:
        calls: list[dict] = []
        backend = _RecordingBackend(
            "EVAL: Physics-informed check.\nGAPS: arc control\nNEXT_ACTION: PROBE\nQ2: What controls arc length?"
        )

        def fake_build_tutor_prompt(user_payload: str, *, cfg: XYZGLConfig, turn_index: int, persona_text: str = ""):
            calls.append({"user_payload": user_payload, "persona_text": persona_text, "turn_index": turn_index})
            return user_payload, _prompt_meta()

        with patch("xyzgl.orchestrator.tutor_phases.build_tutor_prompt", new=fake_build_tutor_prompt):
            with patch("xyzgl.orchestrator.tutor_phases._get_tutor", return_value=backend):
                teach = TeachPhase(
                    node_id="node-1",
                    user_state="learning",
                    budget=TeachingBudget(1, 2, "light"),
                    teaching_block="Keep a tight arc.",
                    question="Q: What controls arc length?",
                    prompt_meta={},
                )
                phase = run_eval_phase(
                    cfg=XYZGLConfig(),
                    seed=7,
                    turn_index=3,
                    node_id="node-1",
                    node_title="Arc Length",
                    teach=teach,
                    mirror_answer="Keep the rod steady.",
                    user_answer="I keep changing the distance.",
                    required_keywords=["arc", "distance"],
                    resonance=0.9,
                    mastery=0.7,
                )

        self.assertEqual(len(calls), 1)
        self.assertIn("PHYSICS: mastery=0.70, resonance=0.90, text_similarity=n/a", calls[0]["user_payload"])
        self.assertEqual(phase.prompt_meta["physics"], {"mastery": 0.7, "resonance": 0.9, "text_similarity": None})

    def test_run_eval_phase_without_physics_stays_backward_compatible(self) -> None:
        calls: list[dict] = []
        backend = _RecordingBackend(
            "EVAL: Needs one more step.\nGAPS: root cause\nNEXT_ACTION: PROBE\nQ2: What did you miss?"
        )

        def fake_build_tutor_prompt(user_payload: str, *, cfg: XYZGLConfig, turn_index: int, persona_text: str = ""):
            calls.append({"user_payload": user_payload, "persona_text": persona_text, "turn_index": turn_index})
            return user_payload, _prompt_meta()

        with patch("xyzgl.orchestrator.tutor_phases.build_tutor_prompt", new=fake_build_tutor_prompt):
            with patch("xyzgl.orchestrator.tutor_phases._get_tutor", return_value=backend):
                teach = TeachPhase(
                    node_id="node-2",
                    user_state="learning",
                    budget=TeachingBudget(1, 2, "light"),
                    teaching_block="Watch the puddle.",
                    question="Q: What is the puddle doing?",
                    prompt_meta={},
                )
                phase = run_eval_phase(
                    cfg=XYZGLConfig(),
                    seed=11,
                    turn_index=4,
                    node_id="node-2",
                    node_title="Puddle Control",
                    teach=teach,
                    mirror_answer=None,
                    user_answer="It moves around.",
                    required_keywords=["puddle"],
                )

        self.assertEqual(len(calls), 1)
        self.assertNotIn("PHYSICS:", calls[0]["user_payload"])
        self.assertNotIn("physics", phase.prompt_meta)

    def test_run_teach_phase_with_persona_sets_persona_injected(self) -> None:
        calls: list[dict] = []
        backend = _RecordingBackend("Safety first: Keep your stickout steady.\nQ: What does a steady stickout change?")

        def fake_build_tutor_prompt(user_payload: str, *, cfg: XYZGLConfig, turn_index: int, persona_text: str = ""):
            calls.append({"user_payload": user_payload, "persona_text": persona_text, "turn_index": turn_index})
            return user_payload, _prompt_meta()

        with patch("xyzgl.orchestrator.tutor_phases.build_tutor_prompt", new=fake_build_tutor_prompt):
            with patch("xyzgl.orchestrator.tutor_phases._get_tutor", return_value=backend):
                phase = run_teach_phase(
                    cfg=XYZGLConfig(),
                    seed=5,
                    turn_index=1,
                    node_id="node-3",
                    node_title="Stickout",
                    node_summary="Keep the wire extension stable.",
                    user_state="confused",
                    budget=TeachingBudget(1, 3, "light"),
                    persona_text="PERSONA: Miller mentor voice",
                )

        self.assertEqual(calls[0]["persona_text"], "PERSONA: Miller mentor voice")
        self.assertTrue(phase.persona_injected)
        self.assertTrue(phase.prompt_meta["persona_injected"])

    def test_run_teach_phase_without_persona_sets_persona_injected_false(self) -> None:
        calls: list[dict] = []
        backend = _RecordingBackend("Safety first: Travel speed changes bead shape.\nQ: What happens if you go too fast?")

        def fake_build_tutor_prompt(user_payload: str, *, cfg: XYZGLConfig, turn_index: int, persona_text: str = ""):
            calls.append({"user_payload": user_payload, "persona_text": persona_text, "turn_index": turn_index})
            return user_payload, _prompt_meta()

        with patch("xyzgl.orchestrator.tutor_phases.build_tutor_prompt", new=fake_build_tutor_prompt):
            with patch("xyzgl.orchestrator.tutor_phases._get_tutor", return_value=backend):
                phase = run_teach_phase(
                    cfg=XYZGLConfig(),
                    seed=13,
                    turn_index=2,
                    node_id="node-4",
                    node_title="Travel Speed",
                    node_summary="Fast travel narrows the bead.",
                    user_state="learning",
                    budget=TeachingBudget(1, 3, "light"),
                )

        self.assertEqual(calls[0]["persona_text"], "")
        self.assertFalse(phase.persona_injected)
        self.assertNotIn("persona_injected", phase.prompt_meta)


if __name__ == "__main__":
    unittest.main()
