from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from .base import LLMBackend
from .fault import FaultBackend
from .gemini import GeminiBackend, GeminiConfig
from .ollama import OllamaBackend, OllamaConfig
from .stub import StubMirrorBackend, StubTutorBackend
from ..config import XYZGLConfig


class BackendConfigError(RuntimeError):
    pass


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    if v is None:
        return None
    v = v.strip()
    return None if v == "" else v


def _is_local_ollama_host(host: str) -> bool:
    try:
        u = urlparse(host)
    except Exception:
        return False
    if u.scheme not in {"http", "https"}:
        return False
    hn = (u.hostname or "").strip().lower()
    if not hn:
        return False
    if hn == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(hn)
        return ip.is_loopback
    except ValueError:
        return False


def get_tutor_backend(cfg: XYZGLConfig) -> LLMBackend:
    """Return the Tutor backend (external fast model)."""

    name = (cfg.tutor_backend or "stub").lower()
    if name == "stub":
        return StubTutorBackend()
    if name == "fault":
        return FaultBackend.from_env(label="tutor_fault")
    if name == "gemini":
        api_key = _env("DAEDALUS_GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
        model = cfg.tutor_model or _env("DAEDALUS_GEMINI_MODEL") or ""
        if not api_key:
            raise BackendConfigError("Missing Gemini API key (DAEDALUS_GEMINI_API_KEY or GOOGLE_API_KEY)")
        if not model:
            raise BackendConfigError("Missing Gemini model name (DAEDALUS_GEMINI_MODEL or cfg.tutor_model)")
        return GeminiBackend(GeminiConfig(api_key=api_key, model=model))

    raise BackendConfigError(f"Unknown tutor backend: {name}")


def get_mirror_backend(cfg: XYZGLConfig) -> LLMBackend:
    """Return the Mirror backend (local model for user simulation)."""

    name = (cfg.mirror_backend or "stub").lower()
    if name in {"stub", "mirror_stub"}:
        return StubMirrorBackend()
    if name == "fault":
        return FaultBackend.from_env(label="mirror_fault")
    if name == "ollama":
        model = cfg.mirror_model or _env("DAEDALUS_OLLAMA_MODEL") or ""
        host = cfg.ollama_host or _env("DAEDALUS_OLLAMA_HOST") or "http://localhost:11434"
        if not model:
            raise BackendConfigError("Missing Ollama model name (DAEDALUS_OLLAMA_MODEL or cfg.mirror_model)")
        if not cfg.allow_remote_ollama and not _is_local_ollama_host(host):
            raise BackendConfigError(
                "Remote Ollama host is blocked by default. "
                "Set DAEDALUS_ALLOW_REMOTE_OLLAMA=1 to allow non-local hosts."
            )
        return OllamaBackend(OllamaConfig(host=host, model=model, allow_remote=bool(cfg.allow_remote_ollama)))

    raise BackendConfigError(f"Unknown mirror backend: {name}")


def require_real_backends() -> bool:
    v = _env("DAEDALUS_REQUIRE_REAL_BACKENDS")
    return v is not None and v.lower() in {"1", "true", "yes", "on"}
