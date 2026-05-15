from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from xyzgl.backends.base import BackendResult, LLMBackend
from xyzgl.config import XYZGLConfig
from xyzgl.orchestrator.mirror import _mirror_context_block as orch_mirror_context_block
from xyzgl.router import _mirror_context_block, route_turn


class _TutorBackend(LLMBackend):
    name = "stub"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        return BackendResult(
            text="Safety first: Let’s work through the bead step by step.",
            backend=self.name,
            model="stub",
            latency_ms=0,
        )


class _SpyMirrorBackend(LLMBackend):
    name = "mirror_stub"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        self.prompts.append(prompt)
        return BackendResult(
            text="I think the learner would answer briefly.",
            backend=self.name,
            model="stub",
            latency_ms=0,
        )


def _extract_payload(prompt: str) -> dict[str, str]:
    prefix = "MIRROR_CONTEXT_JSON: "
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return json.loads(line[len(prefix):])
    raise AssertionError("missing mirror payload")


class Bug05MirrorRedactionExcerptTests(unittest.TestCase):
    def test_router_helper_redacted_mode_exposes_only_metadata(self) -> None:
        secret = "My SIN note is 123-456-789 and the weld gap was 3 mm."
        out = _mirror_context_block(secret, send_raw=False, label="learner")
        self.assertTrue(out.startswith("<redacted:learner> len="))
        self.assertIn("digest=", out)
        self.assertNotIn("SIN", out)
        self.assertNotIn("123-456-789", out)
        self.assertNotIn("weld gap", out)

    def test_orchestrator_helper_redacted_mode_exposes_only_metadata(self) -> None:
        text = "X-Goog-Api-Key: AIzaSySecretValue\nThe student is nervous about root opening."
        out = orch_mirror_context_block(text, send_raw=False, label="session-turn")
        self.assertTrue(out.startswith("<redacted:session-turn> len="))
        self.assertIn("digest=", out)
        self.assertNotIn("AIza", out)
        self.assertNotIn("root opening", out)

    def test_route_turn_redacted_prompt_has_no_excerpt_or_secret_header_content(self) -> None:
        spy = _SpyMirrorBackend()
        cfg = XYZGLConfig(enable_mirror=True, mirror_backend="stub", tutor_backend="stub")
        user_text = (
            "X-Goog-Api-Key: AIzaSySecretValue\n"
            "My bank pin is 4321 and the root opening is 3 mm."
        )

        with patch.dict(os.environ, {}, clear=False):
            with patch("xyzgl.router.get_tutor_backend", return_value=_TutorBackend()):
                with patch("xyzgl.router.get_mirror_backend", return_value=spy):
                    out = route_turn(user_text, cfg=cfg, seed=7)

        self.assertEqual(out["mirror_meta"]["prompt_mode"], "redacted")
        payload = _extract_payload(spy.prompts[-1])
        self.assertTrue(payload["learner"].startswith("<redacted:learner> len="))
        self.assertTrue(payload["tutor"].startswith("<redacted:tutor> len="))
        self.assertNotIn("AIza", payload["learner"])
        self.assertNotIn("4321", payload["learner"])
        self.assertNotIn("root opening", payload["learner"])
        self.assertNotIn("step by step", payload["tutor"])


if __name__ == "__main__":
    unittest.main()
