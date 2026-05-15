from __future__ import annotations

import os
from dataclasses import dataclass

_MAX_ENV_INT_CHARS = 32
_MAX_ENV_STR_CHARS = 8192


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    if v is None:
        return default
    if len(v) > _MAX_ENV_STR_CHARS:
        return default
    s = v.strip()
    return default if s == "" else s


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    if len(v) > _MAX_ENV_STR_CHARS:
        return default
    if v.strip() == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


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


def _env_optional_int(name: str, default: int | None) -> int | None:
    v = os.environ.get(name)
    if v is None:
        return default
    s = v.strip()
    if s == "":
        return default
    if len(s) > _MAX_ENV_INT_CHARS:
        return default
    body = s[1:] if s[:1] in {"+", "-"} else s
    if not body or not body.isdigit():
        return default
    try:
        return int(s)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None:
        return default
    s = v.strip()
    if s == "":
        return default
    if len(s) > _MAX_ENV_STR_CHARS:
        return default
    try:
        return float(s)
    except Exception:
        return default


def _clamp_int(value: int, *, low: int, high: int) -> int:
    try:
        iv = int(value)
    except Exception:
        iv = low
    return max(low, min(high, iv))


MAX_CHARS_IN_HARD = 200_000
MAX_CHARS_OUT_HARD = 200_000
MAX_GROUNDING_SNIPPETS_HARD = 128
MAX_GROUNDING_CHARS_HARD = 200_000
MIN_SAFE_REPLY_CHARS = 15


@dataclass(frozen=True)
class XYZGLConfig:
    """Runtime configuration for XYZGL/Daedalus.

    Design goal:
      - keep defaults deterministic for harnesses
      - allow real backends via env/CLI when explicitly enabled

    Backends (env overrides used by `from_env()`):
      - DAEDALUS_TUTOR_BACKEND: stub | gemini | fault
      - DAEDALUS_MIRROR_BACKEND: stub | ollama | fault
      - DAEDALUS_ENABLE_MIRROR: 1/0
      - DAEDALUS_GEMINI_MODEL
      - DAEDALUS_OLLAMA_MODEL
      - DAEDALUS_OLLAMA_HOST

    Grounding + protocol:
      - DAEDALUS_GROUNDING_MODE: off | local
      - DAEDALUS_GROUNDING_DIR: default 'curriculum'
      - DAEDALUS_GROUNDING_MAX_SNIPPETS: default 6
      - DAEDALUS_GROUNDING_MAX_CHARS: default 3000
      - DAEDALUS_PROTOCOL_PATH: default 'STABLE/ROLE_PROTOCOL.md'
      - DAEDALUS_PROTOCOL_REGROUND_EVERY: default 5 (0 disables periodic regrounding)
      - DAEDALUS_ALLOW_PROTOCOL_FALLBACK: default 0 (invalid protocol paths fail closed)
    """

    # Backends
    tutor_backend: str = "stub"   # external tutor (fast API)
    mirror_backend: str = "stub"  # local mirror (predict user)
    enable_mirror: bool = False
    mirror_send_user_content: bool = False

    # Model names / connection params (optional)
    tutor_model: str = ""         # e.g. gemini-2.5-flash
    mirror_model: str = ""        # e.g. gwen2.5:7b
    ollama_host: str = "http://localhost:11434"
    allow_remote_ollama: bool = False

    # Protocol re-grounding
    protocol_path: str = "STABLE/ROLE_PROTOCOL.md"
    protocol_reground_every: int = 5
    allow_protocol_fallback: bool = False

    # Curriculum grounding (local corpus)
    grounding_mode: str = "off"     # off | local
    grounding_dir: str = "curriculum"
    grounding_max_snippets: int = 6
    grounding_max_chars: int = 3000

    # Safety/UX toggles
    enforce_determinism: bool = True
    max_chars_in: int = 10_000
    max_chars_out: int = 10_000

    # Compatibility (older fields used in schemas/outputs)
    llm_backend: str = "stub"

    # Persona
    persona_enabled: bool = False
    persona_name: str = "Miller"
    persona_role: str = "Gruff Welding Foreman"
    persona_max_words: int = 15

    # Lithosphere / Physics
    lithosphere_enabled: bool = False
    lithosphere_embed_dim: int = 768
    lithosphere_grains: int = 8
    lithosphere_seed: int | None = None
    dna_filename: str = "dna_geometry.bin"
    projection_scale: float = 10.0
    resonance_high_threshold: float = 0.9
    similarity_high_threshold: float = 0.95
    mastery_increment: float = 0.1
    mastery_initial: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_chars_in", _clamp_int(self.max_chars_in, low=1, high=MAX_CHARS_IN_HARD))
        object.__setattr__(self, "max_chars_out", _clamp_int(self.max_chars_out, low=MIN_SAFE_REPLY_CHARS, high=MAX_CHARS_OUT_HARD))
        object.__setattr__(
            self,
            "grounding_max_snippets",
            _clamp_int(self.grounding_max_snippets, low=0, high=MAX_GROUNDING_SNIPPETS_HARD),
        )
        object.__setattr__(
            self,
            "grounding_max_chars",
            _clamp_int(self.grounding_max_chars, low=0, high=MAX_GROUNDING_CHARS_HARD),
        )
        object.__setattr__(self, "protocol_reground_every", _clamp_int(self.protocol_reground_every, low=0, high=10_000))

    @staticmethod
    def from_env() -> "XYZGLConfig":
        tutor_backend = _env("DAEDALUS_TUTOR_BACKEND", "stub")
        mirror_backend = _env("DAEDALUS_MIRROR_BACKEND", "stub")
        enable_mirror = _env_bool("DAEDALUS_ENABLE_MIRROR", False)
        mirror_send_user_content = _env_bool("DAEDALUS_MIRROR_SEND_USER_CONTENT", False)
        tutor_model = _env("DAEDALUS_GEMINI_MODEL", "")
        mirror_model = _env("DAEDALUS_OLLAMA_MODEL", "")
        ollama_host = _env("DAEDALUS_OLLAMA_HOST", "http://localhost:11434")
        allow_remote_ollama = _env_bool("DAEDALUS_ALLOW_REMOTE_OLLAMA", False)

        # Protocol + grounding
        grounding_mode = _env("DAEDALUS_GROUNDING_MODE", "off")
        grounding_dir = _env("DAEDALUS_GROUNDING_DIR", "curriculum")
        grounding_max_snippets = _env_int("DAEDALUS_GROUNDING_MAX_SNIPPETS", 6)
        grounding_max_chars = _env_int("DAEDALUS_GROUNDING_MAX_CHARS", 3000)
        protocol_path = _env("DAEDALUS_PROTOCOL_PATH", "STABLE/ROLE_PROTOCOL.md")
        protocol_reground_every = _env_int("DAEDALUS_PROTOCOL_REGROUND_EVERY", 5)
        allow_protocol_fallback = _env_bool("DAEDALUS_ALLOW_PROTOCOL_FALLBACK", False)
        max_chars_in = _env_int("DAEDALUS_MAX_CHARS_IN", 10_000)
        max_chars_out = _env_int("DAEDALUS_MAX_CHARS_OUT", 10_000)

        persona_enabled = _env_bool("DAEDALUS_PERSONA_ENABLED", False)
        persona_name = _env("DAEDALUS_PERSONA_NAME", "Miller")
        persona_role = _env("DAEDALUS_PERSONA_ROLE", "Gruff Welding Foreman")
        persona_max_words = _env_int("DAEDALUS_PERSONA_MAX_WORDS", 15)

        lithosphere_enabled = _env_bool("DAEDALUS_LITHOSPHERE_ENABLED", False)
        lithosphere_embed_dim = _env_int("DAEDALUS_LITHOSPHERE_EMBED_DIM", 768)
        lithosphere_grains = _env_int("DAEDALUS_LITHOSPHERE_GRAINS", 8)
        lithosphere_seed = _env_optional_int("DAEDALUS_LITHOSPHERE_SEED", None)
        dna_filename = _env("DAEDALUS_DNA_FILENAME", "dna_geometry.bin")
        projection_scale = _env_float("DAEDALUS_LITHOSPHERE_PROJECTION_SCALE", 10.0)
        resonance_high_threshold = _env_float("DAEDALUS_RESONANCE_HIGH_THRESHOLD", 0.9)
        similarity_high_threshold = _env_float("DAEDALUS_SIMILARITY_HIGH_THRESHOLD", 0.95)
        mastery_increment = _env_float("DAEDALUS_MASTERY_INCREMENT", 0.1)
        mastery_initial = _env_float("DAEDALUS_MASTERY_INITIAL", 0.5)

        grounding_max_snippets = _clamp_int(grounding_max_snippets, low=0, high=MAX_GROUNDING_SNIPPETS_HARD)
        grounding_max_chars = _clamp_int(grounding_max_chars, low=0, high=MAX_GROUNDING_CHARS_HARD)
        protocol_reground_every = _clamp_int(protocol_reground_every, low=0, high=10_000)
        max_chars_in = _clamp_int(max_chars_in, low=1, high=MAX_CHARS_IN_HARD)
        max_chars_out = _clamp_int(max_chars_out, low=1, high=MAX_CHARS_OUT_HARD)

        # Keep harness defaults deterministic unless explicitly relaxed.
        enforce_det = _env_bool("DAEDALUS_ENFORCE_DETERMINISM", True)

        return XYZGLConfig(
            tutor_backend=tutor_backend,
            mirror_backend=mirror_backend,
            enable_mirror=enable_mirror,
            mirror_send_user_content=mirror_send_user_content,
            tutor_model=tutor_model,
            mirror_model=mirror_model,
            ollama_host=ollama_host,
            allow_remote_ollama=allow_remote_ollama,
            protocol_path=protocol_path,
            protocol_reground_every=protocol_reground_every,
            allow_protocol_fallback=allow_protocol_fallback,
            grounding_mode=grounding_mode,
            grounding_dir=grounding_dir,
            grounding_max_snippets=grounding_max_snippets,
            grounding_max_chars=grounding_max_chars,
            max_chars_in=max_chars_in,
            max_chars_out=max_chars_out,
            enforce_determinism=enforce_det,
            llm_backend=tutor_backend,
            persona_enabled=persona_enabled,
            persona_name=persona_name,
            persona_role=persona_role,
            persona_max_words=persona_max_words,
            lithosphere_enabled=lithosphere_enabled,
            lithosphere_embed_dim=lithosphere_embed_dim,
            lithosphere_grains=lithosphere_grains,
            lithosphere_seed=lithosphere_seed,
            dna_filename=dna_filename,
            projection_scale=projection_scale,
            resonance_high_threshold=resonance_high_threshold,
            similarity_high_threshold=similarity_high_threshold,
            mastery_increment=mastery_increment,
            mastery_initial=mastery_initial,
        )
