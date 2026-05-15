from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from .base import BackendResult, LLMBackend
from ..util_http import HTTPError, post_json


@dataclass(frozen=True)
class OllamaConfig:
    host: str
    model: str
    timeout_s: float = 60.0
    allow_remote: bool = False


class OllamaBackend(LLMBackend):
    """Local backend via Ollama HTTP API.

    Role: primarily used as the Local Mirror.

    Notes on determinism:
      - We pass `options.seed` and set `temperature=0`.
      - True determinism depends on the installed model/runtime.
    """

    name = "ollama"

    def __init__(self, cfg: OllamaConfig):
        self.cfg = cfg

    @staticmethod
    def _is_local_host(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        host = (parsed.hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    @staticmethod
    def _is_https(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        return (parsed.scheme or "").strip().lower() == "https"

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        url = self.cfg.host.rstrip("/") + "/api/generate"
        env_allow_remote = os.getenv("DAEDALUS_ALLOW_REMOTE_OLLAMA", "").strip().lower() in {"1", "true", "yes"}
        is_local = self._is_local_host(url)
        if not is_local and not (self.cfg.allow_remote or env_allow_remote):
            raise RuntimeError(
                "Refusing non-local Ollama host; set DAEDALUS_ALLOW_REMOTE_OLLAMA=1 to allow remote targets."
            )
        if not is_local and not self._is_https(url):
            raise RuntimeError("Refusing insecure remote Ollama host; use https for non-local targets.")
        options: dict = {
            "temperature": 0,
            "top_p": 1,
            "num_predict": max_tokens if max_tokens is not None else 512,
        }
        if seed is not None:
            options["seed"] = int(seed)

        payload = {
            "model": self.cfg.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        try:
            data, latency_ms = post_json(url, payload, timeout_s=self.cfg.timeout_s)
        except HTTPError as e:
            raise RuntimeError(
                "Ollama call failed. Is Ollama running on DAEDALUS_OLLAMA_HOST and does the model exist? "
                f"details: {e}"
            ) from e

        text = (data.get("response") or "").strip()
        return BackendResult(text=text, backend=self.name, model=self.cfg.model, latency_ms=latency_ms)
