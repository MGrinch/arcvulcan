from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendResult:
    """Normalized backend output.

    Keep this tiny and JSON-friendly so it can be stored in Witness events.
    """

    text: str
    backend: str
    model: str
    latency_ms: int


class LLMBackend:
    """Abstract backend interface.

    Backends must:
      - accept a seed (even if they can't fully honor it)
      - return a BackendResult
      - avoid hidden side effects (no file writes)
    """

    name: str = ""

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        raise NotImplementedError
