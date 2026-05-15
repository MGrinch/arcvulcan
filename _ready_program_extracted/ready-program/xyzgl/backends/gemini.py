from __future__ import annotations

from dataclasses import dataclass, field

from .base import BackendResult, LLMBackend
from ..util_http import HTTPError, post_json

_DEFAULT_MAX_OUTPUT_TOKENS = 1024
_MAX_OUTPUT_TOKENS = 8192


@dataclass(frozen=True)
class GeminiConfig:
    """Connection settings for Gemini via the Generative Language API."""

    api_key: str = field(repr=False)
    model: str
    timeout_s: float = 60.0


class GeminiBackend(LLMBackend):
    """Google Generative Language API backend.

    This uses the REST endpoint (key passed via header):
      https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

    Notes:
      - For reproducibility we default to temperature=0.
      - True determinism cannot be guaranteed for hosted models.
    """

    name = "gemini"

    def __init__(self, cfg: GeminiConfig):
        if not cfg.api_key:
            raise ValueError("GeminiConfig.api_key is required")
        if not cfg.model:
            raise ValueError("GeminiConfig.model is required")
        self.cfg = cfg

    def generate(self, prompt: str, *, seed: int | None, max_tokens: int | None = None) -> BackendResult:
        # Seed is not consistently supported across Gemini REST variants, so we treat it as advisory.
        # REST docs (Jan 2026) use `x-goog-api-key` header rather than `?key=`.
        model = self.cfg.model.strip()
        if model.startswith("models/"):
            model = model[len("models/"):]
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent"

        if max_tokens is None:
            effective_max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS
        else:
            try:
                effective_max_tokens = int(max_tokens)
            except Exception:
                effective_max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS
            if effective_max_tokens <= 0:
                effective_max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS
        effective_max_tokens = min(effective_max_tokens, _MAX_OUTPUT_TOKENS)

        gen_cfg: dict = {
            "temperature": 0,
            "topP": 1,
            "maxOutputTokens": effective_max_tokens,
        }

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg,
        }

        try:
            data, latency_ms = post_json(
                url,
                payload,
                timeout_s=self.cfg.timeout_s,
                headers={"x-goog-api-key": self.cfg.api_key},
            )
        except HTTPError as e:
            raise RuntimeError(
                "Gemini call failed. Set DAEDALUS_GEMINI_API_KEY/GOOGLE_API_KEY and DAEDALUS_GEMINI_MODEL. "
                f"details: {e}"
            ) from e

        text = ""
        try:
            candidates = data.get("candidates") or []
            if candidates:
                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if parts:
                    text = (parts[0].get("text") or "").strip()
        except Exception:
            # Keep best-effort parsing; include raw in error paths if needed.
            text = ""

        if not text:
            raise RuntimeError(
                "Gemini response parse failed: empty text in candidates/content/parts. "
                f"top_level_keys={list(data.keys())}"
            )

        return BackendResult(text=text, backend=self.name, model=self.cfg.model, latency_ms=latency_ms)
