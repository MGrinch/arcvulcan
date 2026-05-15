from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from xyzgl.config import XYZGLConfig
import backend_contract_probe as probe_mod
import backend_fault_injector as injector_mod

_SECRET = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"


class _FakeResult:
    def __init__(self) -> None:
        self.text = "Deterministic tutor reply."
        self.backend = "stub"
        self.model = "stub-model"
        self.latency_ms = 5


class _PrintingBackend:
    def generate(self, prompt: str, *, seed: int | None):
        print(f"Authorization: Bearer {_SECRET}")
        print(f"stderr token={_SECRET}", file=sys.stderr)
        return _FakeResult()


class _CleanBackend:
    def generate(self, prompt: str, *, seed: int | None):
        return _FakeResult()


def test_backend_contract_probe_fails_closed_on_generate_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: _PrintingBackend())

    out = probe_mod._probe_one("tutor", "stub", cfg=XYZGLConfig(), seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert "stdout/stderr side effects" in out["error"]
    assert out["side_effect_stage"] == "generate"
    assert out["side_effects"]["stdout_present"] is True
    assert out["side_effects"]["stderr_present"] is True
    dumped = json.dumps(out, sort_keys=True)
    assert _SECRET not in dumped
    assert "stdout_len" in dumped
    assert "stderr_len" in dumped


def test_backend_contract_probe_fails_closed_on_backend_init_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_tutor_backend(cfg: XYZGLConfig):
        print(f"init secret {_SECRET}")
        return _CleanBackend()

    monkeypatch.setattr(probe_mod, "get_tutor_backend", fake_get_tutor_backend)

    out = probe_mod._probe_one("tutor", "stub", cfg=XYZGLConfig(), seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert out["side_effect_stage"] == "backend_init"
    dumped = json.dumps(out, sort_keys=True)
    assert _SECRET not in dumped


def test_backend_fault_injector_marks_handled_route_side_effects_as_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from xyzgl import router as router_mod

    def fake_route_turn(*args, **kwargs):
        print(f"route leaked {_SECRET}")
        return {
            "reply": "stub fallback reply",
            "backend_error": "handled backend error",
            "effective_backend": "stub",
            "requested_backend": "fault",
            "mirror_prediction": None,
        }

    monkeypatch.setattr(router_mod, "route_turn", fake_route_turn)

    out = injector_mod._scenario(
        "tutor_fault_exception_fallback",
        expect_raise=False,
        env={},
        expect_effective_backend="stub",
        require_backend_error=True,
    )

    assert out["pass"] is False
    assert "stdout/stderr side effects" in out["details"]
    dumped = json.dumps(out, sort_keys=True)
    assert _SECRET not in dumped
    assert out["observed"]["side_effects"]["stdout_present"] is True
