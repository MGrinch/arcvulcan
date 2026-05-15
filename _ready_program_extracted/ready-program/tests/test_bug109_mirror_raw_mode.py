from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from xyzgl.backends.base import BackendResult, LLMBackend
from xyzgl.config import XYZGLConfig
from xyzgl.router import _mirror_context_block, route_turn


class _TutorBackend(LLMBackend):
    name = "stub"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        return BackendResult(
            text="Safety first: Tutor reply with authorization: Bearer tutor-secret",
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
            text="I think: mirror reply",
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


class Bug109MirrorRawModeTests(unittest.TestCase):
    def test_helper_returns_bounded_raw_text_when_enabled(self) -> None:
        secret = "authorization: Bearer abc123\napi_key=shhh"
        out = _mirror_context_block(secret, send_raw=True, label="learner")
        self.assertEqual(out, secret)

    def test_helper_redacts_when_raw_disabled(self) -> None:
        secret = "authorization: Bearer abc123\napi_key=shhh"
        out = _mirror_context_block(secret, send_raw=False, label="learner")
        self.assertTrue(out.startswith("<redacted:learner>"))
        self.assertNotIn("abc123", out)
        self.assertNotIn("shhh", out)

    def test_route_turn_sends_raw_payload_and_reports_raw_mode(self) -> None:
        spy = _SpyMirrorBackend()
        cfg = XYZGLConfig(enable_mirror=True, mirror_backend="stub", tutor_backend="stub")
        user_text = "authorization: Bearer abc123\nhttps://example.com/?token=sekret"

        with patch.dict(os.environ, {"DAEDALUS_MIRROR_SEND_USER_CONTENT": "1"}, clear=False):
            with patch("xyzgl.router.get_tutor_backend", return_value=_TutorBackend()):
                with patch("xyzgl.router.get_mirror_backend", return_value=spy):
                    out = route_turn(user_text, cfg=cfg, seed=7)

        self.assertEqual(out["mirror_meta"]["prompt_mode"], "raw")
        payload = _extract_payload(spy.prompts[-1])
        self.assertEqual(payload["learner"], user_text)
        self.assertIn("authorization: Bearer abc123", payload["learner"])
        self.assertIn("token=sekret", payload["learner"])

    def test_route_turn_redacts_payload_when_raw_disabled(self) -> None:
        spy = _SpyMirrorBackend()
        cfg = XYZGLConfig(enable_mirror=True, mirror_backend="stub", tutor_backend="stub")
        user_text = "authorization: Bearer abc123\nhttps://example.com/?token=sekret"

        with patch.dict(os.environ, {}, clear=False):
            with patch("xyzgl.router.get_tutor_backend", return_value=_TutorBackend()):
                with patch("xyzgl.router.get_mirror_backend", return_value=spy):
                    out = route_turn(user_text, cfg=cfg, seed=7)

        self.assertEqual(out["mirror_meta"]["prompt_mode"], "redacted")
        payload = _extract_payload(spy.prompts[-1])
        self.assertTrue(payload["learner"].startswith("<redacted:learner>"))
        self.assertNotIn("abc123", payload["learner"])
        self.assertNotIn("token=sekret", payload["learner"])


if __name__ == "__main__":
    unittest.main()
