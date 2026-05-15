from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl.grounding import corpus as corpus_module
from xyzgl.grounding import prompting as prompting_module
from xyzgl.grounding.prompting import build_grounding


def _write_passage_cap_corpus(root: Path) -> None:
    sources_dir = root / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    filler_chunks = [((f"generic filler paragraph {idx} ") * 45).strip() for idx in range(20)]
    (sources_dir / "filler.md").write_text("\n\n".join(filler_chunks) + "\n", encoding="utf-8")
    (sources_dir / "target.md").write_text("rare_target_token retrieval anchor\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "filler",
                        "title": "Filler",
                        "path": "sources/filler.md",
                        "tags": [],
                        "license": "demo",
                    },
                    {
                        "id": "target",
                        "title": "Target",
                        "path": "sources/target.md",
                        "tags": [],
                        "license": "demo",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _clear_grounding_cache() -> None:
    prompting_module._CORPUS_CACHE.clear()
    yield
    prompting_module._CORPUS_CACHE.clear()


def test_load_corpus_distributes_passage_budget_across_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "curriculum"
    _write_passage_cap_corpus(corpus_dir)

    monkeypatch.setattr(corpus_module, "MAX_PASSAGES", 10)

    corpus = corpus_module.load_corpus(corpus_dir)

    assert len(corpus.passages) == 10
    assert {p.source_id for p in corpus.passages} == {"filler", "target"}
    assert any(w.startswith("passage_limit_exhausted:10>=10;") for w in corpus.warnings)
    assert corpus.stats["truncated_sources_due_to_passage_cap"] == 1
    assert corpus.stats["omitted_passages_due_to_passage_cap"] > 0
    assert corpus.stats["passage_allocation_strategy"] == "round_robin_by_source"


def test_build_grounding_keeps_late_target_visible_under_passage_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus_dir = tmp_path / "curriculum"
    _write_passage_cap_corpus(corpus_dir)

    monkeypatch.setattr(corpus_module, "MAX_PASSAGES", 10)

    text, meta = build_grounding(corpus_dir, "rare_target_token", max_snippets=3, max_chars=600)

    assert "rare_target_token retrieval anchor" in text
    assert "[src:target:0]" in text
    assert any(w.startswith("passage_limit_exhausted:10>=10;") for w in meta["warnings"])
    assert meta["corpus_stats"]["truncated_sources_due_to_passage_cap"] == 1
