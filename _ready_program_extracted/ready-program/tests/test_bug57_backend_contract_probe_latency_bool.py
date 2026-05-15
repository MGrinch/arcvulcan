from __future__ import annotations

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


class _FakeResult:
    def __init__(self, *, latency_ms: object) -> None:
        self.text = "Deterministic tutor reply."
        self.backend = "stub"
        self.model = "stub-model"
        self.latency_ms = latency_ms


class _FakeBackend:
    def __init__(self, result: _FakeResult) -> None:
        self._result = result

    def generate(self, prompt: str, *, seed: int | None):
        return self._result


@pytest.fixture
def cfg() -> XYZGLConfig:
    return XYZGLConfig()


@pytest.mark.parametrize("latency_ms", [True, False])
def test_probe_one_rejects_boolean_latency_values(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
    latency_ms: bool,
) -> None:
    fake = _FakeBackend(_FakeResult(latency_ms=latency_ms))
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert out["error"] == f"latency_ms invalid: {latency_ms!r}"


def test_probe_one_accepts_non_boolean_integer_latency(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
) -> None:
    fake = _FakeBackend(_FakeResult(latency_ms=0))
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "PASS"
    assert out["meta"]["latency_ms"] == 0
