from __future__ import annotations

"""Fault-injection backend.

This backend exists ONLY to test failure handling, fallbacks, and strict-mode
behavior without requiring network access.

Enable via env:
  DAEDALUS_TUTOR_BACKEND=fault
  DAEDALUS_MIRROR_BACKEND=fault

Control behavior:
  DAEDALUS_FAULT_MODE=exception|timeout|empty|slow
  DAEDALUS_FAULT_DELAY_MS=50
"""

import os
import time
from dataclasses import dataclass

from .base import BackendResult, LLMBackend

_MAX_ENV_INT_CHARS = 16
_MAX_ENV_STR_CHARS = 128


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    if v is None:
        return default
    if len(v) > _MAX_ENV_STR_CHARS:
        return default
    s = v.strip()
    return default if s == "" else s


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    s = v.strip()
    if len(s) > _MAX_ENV_INT_CHARS:
        return default
    body = s[1:] if s[:1] in {"+", "-"} else s
    if not body or not body.isdigit():
        return default
    try:
        return int(s)
    except Exception:
        return default


@dataclass(frozen=True)
class FaultConfig:
    mode: str = "exception"
    delay_ms: int = 0
    label: str = "fault"


class FaultBackend(LLMBackend):
    """Backend that intentionally misbehaves in controlled ways."""

    def __init__(self, cfg: FaultConfig):
        self.cfg = cfg
        self.name = cfg.label

    @staticmethod
    def from_env(*, label: str) -> "FaultBackend":
        mode = _env("DAEDALUS_FAULT_MODE", "exception").lower()
        delay = _env_int("DAEDALUS_FAULT_DELAY_MS", 0)
        return FaultBackend(FaultConfig(mode=mode, delay_ms=delay, label=label))

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        t0 = time.monotonic()
        mode = (self.cfg.mode or "exception").lower()

        if mode == "timeout":
            raise TimeoutError("fault injected timeout")
        if mode == "exception":
            raise RuntimeError("fault injected exception")
        if mode == "slow":
            ms = max(0, int(self.cfg.delay_ms))
            time.sleep(min(ms, 250) / 1000.0)
            text = "(fault backend) slow path reply"
        elif mode == "empty":
            text = ""
        else:
            raise ValueError("unknown fault mode")

        latency_ms = int((time.monotonic() - t0) * 1000)
        # Keep the configured label (for example: tutor_fault vs mirror_fault).
        return BackendResult(text=text, backend=self.name, model=mode, latency_ms=latency_ms)
