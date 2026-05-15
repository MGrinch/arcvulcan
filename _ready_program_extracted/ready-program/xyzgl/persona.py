from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .config import MAX_CHARS_OUT_HARD, XYZGLConfig


@dataclass(frozen=True)
class PersonaConfig:
    """Configuration for the tutor persona voice layer."""

    name: str = "Miller"
    role: str = "Gruff Welding Foreman"
    high_res_behavior: str = "Give a brief approving nod, then push for deeper understanding."
    mid_res_behavior: str = "Acknowledge partial understanding, point out what's missing."
    low_res_behavior: str = "Be direct and forceful about what's wrong. No sugarcoating."
    max_voice_words: int = 15
    res_high_threshold: float = 0.8
    res_low_threshold: float = 0.3


def _coerce_unit_interval(value: float, *, default: float = 0.0) -> float:
    """Return a finite float clamped to the inclusive unit interval."""

    try:
        fvalue = float(value)
    except Exception:
        fvalue = default
    if not isfinite(fvalue):
        fvalue = default
    return max(0.0, min(1.0, fvalue))


def _coerce_positive_int(value: int, *, default: int) -> int:
    """Return a positive integer, falling back to the provided default."""

    try:
        ivalue = int(value)
    except Exception:
        ivalue = default
    return ivalue if ivalue > 0 else default


def _select_behavior(cfg: PersonaConfig, *, resonance: float) -> tuple[str, str]:
    """Select the persona behavior guidance for the given resonance value."""

    if resonance >= _coerce_unit_interval(cfg.res_high_threshold, default=0.8):
        return "high", str(cfg.high_res_behavior)
    if resonance <= _coerce_unit_interval(cfg.res_low_threshold, default=0.3):
        return "low", str(cfg.low_res_behavior)
    return "mid", str(cfg.mid_res_behavior)


def _cap_output(text: str) -> str:
    """Cap persona output to the hard output limit."""

    if len(text) <= MAX_CHARS_OUT_HARD:
        return text
    return text[:MAX_CHARS_OUT_HARD]


def build_persona_instruction(cfg: PersonaConfig, *, mastery: float, resonance: float) -> str:
    """Build a plain-text persona instruction block for tutor prompts."""

    mastery_value = _coerce_unit_interval(mastery)
    resonance_value = _coerce_unit_interval(resonance)
    level, behavior = _select_behavior(cfg, resonance=resonance_value)
    max_voice_words = _coerce_positive_int(cfg.max_voice_words, default=15)

    if level == "high":
        resonance_line = f"Resonance is high — {behavior}"
    elif level == "low":
        resonance_line = f"Resonance is low — {behavior}"
    else:
        resonance_line = f"Resonance is mid-range — {behavior}"

    instruction = "\n".join(
        [
            f"PERSONA: {cfg.name} ({cfg.role})",
            f"Physics: Mastery={mastery_value:.2f}, Resonance={resonance_value:.2f}",
            resonance_line,
            f"Keep persona voice under {max_voice_words} words, then teach normally.",
        ]
    )
    return _cap_output(instruction)


def persona_from_config(xyzgl_cfg: XYZGLConfig) -> PersonaConfig | None:
    """Build a persona configuration from runtime config, or None when disabled."""

    enabled = getattr(xyzgl_cfg, "persona_enabled", True)
    if not bool(enabled):
        return None

    return PersonaConfig(
        name=str(getattr(xyzgl_cfg, "persona_name", PersonaConfig.name)),
        role=str(getattr(xyzgl_cfg, "persona_role", PersonaConfig.role)),
        high_res_behavior=str(
            getattr(xyzgl_cfg, "persona_high_res_behavior", PersonaConfig.high_res_behavior)
        ),
        mid_res_behavior=str(
            getattr(xyzgl_cfg, "persona_mid_res_behavior", PersonaConfig.mid_res_behavior)
        ),
        low_res_behavior=str(
            getattr(xyzgl_cfg, "persona_low_res_behavior", PersonaConfig.low_res_behavior)
        ),
        max_voice_words=_coerce_positive_int(
            getattr(xyzgl_cfg, "persona_max_words", PersonaConfig.max_voice_words),
            default=PersonaConfig.max_voice_words,
        ),
        res_high_threshold=_coerce_unit_interval(
            getattr(xyzgl_cfg, "persona_res_high_threshold", PersonaConfig.res_high_threshold),
            default=PersonaConfig.res_high_threshold,
        ),
        res_low_threshold=_coerce_unit_interval(
            getattr(xyzgl_cfg, "persona_res_low_threshold", PersonaConfig.res_low_threshold),
            default=PersonaConfig.res_low_threshold,
        ),
    )
