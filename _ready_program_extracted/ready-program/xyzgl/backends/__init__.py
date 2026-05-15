"""LLM backend implementations.

Backends are intentionally small and dependency-light:
  - `stub` keeps harnesses deterministic
  - `ollama` talks to a local Ollama server for the Mirror role
  - `gemini` talks to Google Generative Language API for the Tutor role

See `xyzgl/backends/registry.py` for the canonical dispatch layer.
"""
