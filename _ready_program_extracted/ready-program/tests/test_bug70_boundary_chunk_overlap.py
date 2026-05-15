from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from xyzgl.grounding.corpus import _chunk_text, load_corpus
from xyzgl.grounding.retrieval import retrieve_snippets


def _write_corpus(tmp_path: Path, target_text: str, poison_text: str) -> Path:
    root = tmp_path / "curriculum"
    sources = root / "sources"
    sources.mkdir(parents=True)
    (sources / "target.txt").write_text(target_text, encoding="utf-8")
    (sources / "poison.txt").write_text(poison_text, encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {"id": "target", "title": "Target", "path": "sources/target.txt"},
                    {"id": "poison", "title": "Poison", "path": "sources/poison.txt"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def test_hard_split_uses_deterministic_overlap() -> None:
    text = ("x" * 795) + " fit up root opening must stay consistent to prevent burn through"
    chunks_a = _chunk_text(text, max_chars=800)
    chunks_b = _chunk_text(text, max_chars=800)

    assert chunks_a == chunks_b
    assert len(chunks_a) == 2
    assert "fit up root opening" in chunks_a[1]
    assert chunks_a[1].startswith("fit up root opening")


def test_boundary_spanning_clean_evidence_is_returned_with_full_phrase(tmp_path: Path) -> None:
    filler = "x" * 795
    root = _write_corpus(
        tmp_path,
        filler + " fit up root opening must stay consistent to prevent burn through and distortion",
        "fit up root opening distortion warning",
    )

    corpus = load_corpus(root)
    snippets = retrieve_snippets(corpus, "fit up root opening burn through", max_snippets=2)
    target_snippets = [snippet for snippet in snippets if snippet.source_id == "target"]

    assert target_snippets
    assert any(snippet.passage_ordinal == 1 for snippet in target_snippets)
    assert any(
        "fit up root opening must stay consistent" in snippet.excerpt and "burn through" in snippet.excerpt
        for snippet in target_snippets
    )
