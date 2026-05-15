from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from xyzgl.config import XYZGLConfig
import backend_contract_probe as probe_mod


class _FakeResult:
    def __init__(self, *, text: str, backend: str, model: str, latency_ms: int) -> None:
        self.text = text
        self.backend = backend
        self.model = model
        self.latency_ms = latency_ms


class _FakeBackend:
    def __init__(self, result: _FakeResult) -> None:
        self._result = result

    def generate(self, prompt: str, *, seed: int | None):
        return self._result


@pytest.fixture
def cfg() -> XYZGLConfig:
    return XYZGLConfig()


def test_probe_one_rejects_spoofed_backend_identity_for_stub_tutor(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
) -> None:
    fake = _FakeBackend(
        _FakeResult(
            text="Deterministic tutor reply.",
            backend="spoofed-backend",
            model="stub-model",
            latency_ms=5,
        )
    )
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert "backend label mismatch" in out["error"]
    assert "spoofed-backend" in out["error"]


def test_probe_one_rejects_empty_model_even_when_backend_label_matches(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
) -> None:
    fake = _FakeBackend(
        _FakeResult(
            text="Deterministic tutor reply.",
            backend="stub",
            model="   ",
            latency_ms=5,
        )
    )
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert out["error"] == "model field empty or whitespace"


def test_probe_one_accepts_matching_stub_identity_with_non_empty_model(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
) -> None:
    fake = _FakeBackend(
        _FakeResult(
            text="Deterministic tutor reply.",
            backend="stub",
            model="stub-model",
            latency_ms=5,
        )
    )
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "PASS"
    assert out["meta"]["backend"] == "stub"
    assert out["meta"]["model"] == "stub-model"
