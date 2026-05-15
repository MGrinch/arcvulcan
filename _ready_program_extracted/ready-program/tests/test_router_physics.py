from __future__ import annotations

from contextlib import ExitStack, contextmanager
import sys
import types
import unittest
from unittest.mock import patch

from xyzgl.backends.base import BackendResult, LLMBackend
from xyzgl.config import XYZGLConfig
from xyzgl.router import route_turn


class _DeterministicTutorBackend(LLMBackend):
    name = "stub"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        return BackendResult(
            text="Safety first: Deterministic stub tutor reply.",
            backend=self.name,
            model="stub",
            latency_ms=0,
        )


class RouterPhysicsTests(unittest.TestCase):
    def _make_cfg(self, **attrs: object) -> XYZGLConfig:
        cfg = XYZGLConfig()
        for key, value in attrs.items():
            object.__setattr__(cfg, key, value)
        return cfg

    @contextmanager
    def _patched_router_environment(self):
        persona_mod = types.ModuleType("xyzgl.persona")

        def persona_from_config(cfg: XYZGLConfig) -> object | None:
            return object() if bool(getattr(cfg, "persona_enabled", False)) else None

        def build_persona_instruction(_cfg: object, *, mastery: float, resonance: float) -> str:
            return (
                "PERSONA: Miller (Gruff Welding Foreman)\n"
                f"Physics: Mastery={mastery:.2f}, Resonance={resonance:.2f}"
            )

        persona_mod.persona_from_config = persona_from_config
        persona_mod.build_persona_instruction = build_persona_instruction

        knowledge_pkg = types.ModuleType("xyzgl.knowledge")
        knowledge_pkg.__path__ = []  # mark as package for relative imports

        embeddings_mod = types.ModuleType("xyzgl.knowledge.embeddings")

        def text_to_vector(text: str, *, dim: int = 768) -> list[float]:
            base = sum(ord(ch) for ch in text)
            return [((base + (i * 17)) % 97) / 97.0 for i in range(dim)]

        embeddings_mod.text_to_vector = text_to_vector

        lithosphere_mod = types.ModuleType("xyzgl.knowledge.lithosphere")

        class Lithosphere:
            def __init__(self, *, embed_dim: int = 768, grains: int = 8, seed: int | None = None) -> None:
                self.embed_dim = embed_dim
                self.grains = grains
                self.seed = 0 if seed is None else int(seed)
                self._mastery: dict[str, float] = {}

            def get_or_create(self, node_id: str, vec: list[float], text: str) -> dict[str, str]:
                score = sum(vec) + self.seed + self.grains + len(text)
                self._mastery[node_id] = (score % 100) / 100.0
                return {"id": node_id}

            def compute_resonance(self, node_id: str, vec: list[float]) -> float:
                score = sum(vec) + self.seed + self.embed_dim + self.grains + len(node_id)
                return (score % 1000) / 1000.0

            def get_mastery(self, node_id: str) -> float:
                return self._mastery.get(node_id, 0.0)

        lithosphere_mod.Lithosphere = Lithosphere

        def fake_build_tutor_prompt(
            user_text: str,
            *,
            cfg: XYZGLConfig,
            turn_index: int,
            persona_text: str = "",
        ) -> tuple[str, dict[str, object]]:
            prompt = f"PROMPT[{turn_index}]::{persona_text}::{user_text}"
            meta = {
                "protocol_regrounded": False,
                "protocol_path": "STABLE/ROLE_PROTOCOL.md",
                "protocol_loaded": True,
                "protocol_fallback": False,
                "grounding_enabled": False,
                "grounding": {},
                "persona_injected": bool(persona_text),
            }
            return prompt, meta

        with patch.dict(
            sys.modules,
            {
                "xyzgl.persona": persona_mod,
                "xyzgl.knowledge": knowledge_pkg,
                "xyzgl.knowledge.embeddings": embeddings_mod,
                "xyzgl.knowledge.lithosphere": lithosphere_mod,
            },
            clear=False,
        ):
            with ExitStack() as stack:
                stack.enter_context(patch("xyzgl.router.build_tutor_prompt", new=fake_build_tutor_prompt))
                stack.enter_context(patch("xyzgl.router.get_tutor_backend", new=lambda cfg: _DeterministicTutorBackend()))
                stack.enter_context(patch("xyzgl.router.require_real_backends", return_value=False))
                yield

    def test_default_config_has_no_physics_key(self) -> None:
        cfg = self._make_cfg()
        with self._patched_router_environment():
            out = route_turn("arc length", cfg=cfg, seed=7)

        self.assertNotIn("physics", out)

    def test_lithosphere_enabled_adds_physics_block(self) -> None:
        cfg = self._make_cfg(
            lithosphere_enabled=True,
            lithosphere_seed=7,
            lithosphere_embed_dim=8,
            lithosphere_grains=4,
        )
        with self._patched_router_environment():
            out = route_turn("arc length", cfg=cfg, seed=7)

        self.assertIn("physics", out)
        self.assertEqual(
            set(out["physics"].keys()),
            {"mastery", "resonance", "text_similarity", "mastery_delta"},
        )

    def test_persona_enabled_sets_prompt_meta_persona_active(self) -> None:
        cfg = self._make_cfg(
            persona_enabled=True,
            persona_name="Miller",
            persona_role="Gruff Welding Foreman",
            persona_max_words=15,
        )
        with self._patched_router_environment():
            out = route_turn("travel speed", cfg=cfg, seed=5)

        self.assertTrue(out["prompt_meta"].get("persona_active"))

    def test_both_enabled_exposes_persona_and_physics(self) -> None:
        cfg = self._make_cfg(
            persona_enabled=True,
            persona_name="Miller",
            persona_role="Gruff Welding Foreman",
            persona_max_words=15,
            lithosphere_enabled=True,
            lithosphere_seed=11,
            lithosphere_embed_dim=8,
            lithosphere_grains=4,
        )
        with self._patched_router_environment():
            out = route_turn("heat control", cfg=cfg, seed=11)

        self.assertIn("physics", out)
        self.assertTrue(out["prompt_meta"].get("persona_active"))

    def test_same_seed_and_input_produce_same_physics_values(self) -> None:
        cfg = self._make_cfg(
            lithosphere_enabled=True,
            lithosphere_seed=13,
            lithosphere_embed_dim=8,
            lithosphere_grains=4,
        )
        with self._patched_router_environment():
            first = route_turn("fit up", cfg=cfg, seed=19)
            second = route_turn("fit up", cfg=cfg, seed=19)

        self.assertEqual(first["physics"], second["physics"])


if __name__ == "__main__":
    unittest.main()
