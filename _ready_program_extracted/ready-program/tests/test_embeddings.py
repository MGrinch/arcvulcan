from __future__ import annotations

import numpy as np

from xyzgl.knowledge.embeddings import compute_text_similarity, safe_normalize, text_to_vector


def test_text_to_vector_is_deterministic() -> None:
    assert text_to_vector("hello") == text_to_vector("hello")


def test_text_to_vector_dimension_matches_requested_size() -> None:
    assert len(text_to_vector("x", dim=768)) == 768


def test_different_texts_produce_different_vectors() -> None:
    assert text_to_vector("a") != text_to_vector("b")


def test_seed_offset_changes_output() -> None:
    assert text_to_vector("a", seed_offset=0) != text_to_vector("a", seed_offset=1)


def test_empty_text_returns_all_zeros() -> None:
    assert all(x == 0.0 for x in text_to_vector(""))


def test_safe_normalize_keeps_unit_vectors_and_zero_vectors_safe() -> None:
    unit = np.array([0.6, 0.8], dtype=np.float64)
    normalized_unit = safe_normalize(unit)
    assert np.allclose(normalized_unit, unit)
    assert np.isclose(np.linalg.norm(normalized_unit), 1.0)

    zero = np.zeros(3, dtype=np.float64)
    normalized_zero = safe_normalize(zero)
    assert np.array_equal(normalized_zero, zero)


def test_compute_text_similarity_handles_identical_and_different_strings() -> None:
    assert compute_text_similarity("same text", "same text") == 1.0
    assert compute_text_similarity("abc", "xyz") < 0.25


def test_compute_text_similarity_handles_empty_inputs() -> None:
    assert compute_text_similarity("", "") == 1.0
    assert compute_text_similarity("", "non-empty") == 0.0
    assert compute_text_similarity("non-empty", "") == 0.0
