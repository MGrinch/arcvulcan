from __future__ import annotations

import hashlib
from difflib import SequenceMatcher

import numpy as np


# ------------------------------------------------------------------------------
# SECTOR 1: EMBEDDINGS FOUNDATION
# ------------------------------------------------------------------------------

DEFAULT_EMBED_DIM = 768
MAX_TEXT_CHARS = 50_000
_NORMALIZE_EPSILON = 1e-9
_SHA256_MODULUS = 1 << 256


__all__ = [
    "DEFAULT_EMBED_DIM",
    "MAX_TEXT_CHARS",
    "compute_text_similarity",
    "safe_normalize",
    "text_to_vector",
]


def _cap_text(text: str) -> str:
    return text[:MAX_TEXT_CHARS]


def _seed_from_text(text: str, *, seed_offset: int) -> int:
    hash_int = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return (hash_int + int(seed_offset)) % _SHA256_MODULUS


def safe_normalize(v: np.ndarray) -> np.ndarray:
    """Return a unit-length copy of ``v``.

    Zero vectors and numerically tiny vectors return an all-zero array of the
    same shape instead of raising or producing ``nan`` values.
    """
    arr = np.asarray(v, dtype=np.float64)
    norm = float(np.linalg.norm(arr))
    if norm <= _NORMALIZE_EPSILON:
        return np.zeros_like(arr, dtype=np.float64)
    return arr / norm


def text_to_vector(text: str, *, dim: int = DEFAULT_EMBED_DIM, seed_offset: int = 0) -> list[float]:
    """Convert text into a deterministic standard-normal embedding vector.

    The seed is derived from the SHA-256 hash of the capped UTF-8 text, with an
    optional ``seed_offset`` applied inside the SHA-256 integer space so the
    seed always remains non-negative and deterministic.
    """
    dim = int(dim)
    if dim < 1:
        raise ValueError(f"dim must be >= 1, got {dim}")

    capped_text = _cap_text(text)
    if capped_text == "":
        return [0.0] * dim

    rng = np.random.default_rng(_seed_from_text(capped_text, seed_offset=seed_offset))
    return rng.standard_normal(dim).tolist()


def compute_text_similarity(a: str, b: str) -> float:
    """Compute deterministic text similarity using case-insensitive sequence matching.

    Inputs are capped to ``MAX_TEXT_CHARS`` before comparison to bound runtime.
    Returns ``1.0`` when both inputs are empty and ``0.0`` when exactly one is
    empty.
    """
    capped_a = _cap_text(a)
    capped_b = _cap_text(b)

    if capped_a == "" and capped_b == "":
        return 1.0
    if capped_a == "" or capped_b == "":
        return 0.0

    return float(SequenceMatcher(None, capped_a.lower(), capped_b.lower()).ratio())
