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
    def __init__(self, *, text: str, backend: str = "stub", model: str = "stub-model", latency_ms: int = 5) -> None:
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


@pytest.mark.parametrize("text", ["", "   \n\t  "])
def test_probe_one_rejects_empty_or_whitespace_only_text(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
    text: str,
) -> None:
    fake = _FakeBackend(_FakeResult(text=text))
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "FAIL"
    assert out["error"] == "text field empty or whitespace"


def test_probe_one_accepts_nonempty_text(
    monkeypatch: pytest.MonkeyPatch,
    cfg: XYZGLConfig,
) -> None:
    fake = _FakeBackend(_FakeResult(text="Deterministic tutor reply."))
    monkeypatch.setattr(probe_mod, "get_tutor_backend", lambda cfg: fake)

    out = probe_mod._probe_one("tutor", "stub", cfg=cfg, seed=7, allow_network=False)

    assert out["status"] == "PASS"
    assert out["meta"]["text_len"] == len("Deterministic tutor reply.")
