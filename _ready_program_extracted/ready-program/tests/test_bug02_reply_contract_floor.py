from __future__ import annotations

from unittest.mock import patch

from xyzgl.backends.base import BackendResult, LLMBackend
from xyzgl.config import MIN_SAFE_REPLY_CHARS, XYZGLConfig
from xyzgl.router import route_turn
from xyzgl.welding_tutor import SAFETY_PREFIX


class _BareTutorBackend(LLMBackend):
    name = "tutor_fault"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        return BackendResult(
            text="ok",
            backend=self.name,
            model="fault",
            latency_ms=0,
        )


def test_xyzgl_config_floors_max_chars_out_to_preserve_prefixed_reply_body() -> None:
    cfg = XYZGLConfig(max_chars_out=1)
    assert cfg.max_chars_out == MIN_SAFE_REPLY_CHARS


def test_route_turn_preserves_contract_when_cfg_max_chars_out_is_force_mutated_low() -> None:
    cfg = XYZGLConfig()
    object.__setattr__(cfg, "max_chars_out", 1)

    with patch("xyzgl.router.get_tutor_backend", return_value=_BareTutorBackend()), patch(
        "xyzgl.router.require_real_backends", return_value=False
    ):
        out = route_turn("slag inclusion", cfg=cfg, seed=7)

    assert out["reply"].startswith(SAFETY_PREFIX)
    assert len(out["reply"]) >= MIN_SAFE_REPLY_CHARS
    assert out["reply"] == f"{SAFETY_PREFIX}o"
