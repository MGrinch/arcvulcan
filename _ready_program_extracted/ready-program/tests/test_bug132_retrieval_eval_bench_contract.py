from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from xyzgl.grounding.corpus import load_corpus


def _load_bench_module():
    spec = importlib.util.spec_from_file_location(
        "retrieval_eval_bench_under_test", REPO_ROOT / "tools" / "retrieval_eval_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_shipped_benchmark_covers_multiple_expected_sources() -> None:
    bench = json.loads((REPO_ROOT / "curriculum" / "retrieval_bench.json").read_text(encoding="utf-8"))
    cases = bench["cases"]
    expected_source_ids = {
        str(source_id)
        for case in cases
        for source_id in (case.get("expect_source_ids") or [])
        if str(source_id).strip()
    }
    corpus = load_corpus(REPO_ROOT / "curriculum")
    corpus_source_ids = {source.id for source in corpus.sources}

    assert len(cases) >= 4
    assert len(expected_source_ids) >= 2
    assert expected_source_ids.issubset(corpus_source_ids)
    assert len(corpus_source_ids) >= 2


def test_vacuous_shipped_benchmark_contract_is_rejected(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    curriculum = fake_repo / "curriculum"
    sources = curriculum / "sources"
    sources.mkdir(parents=True)
    (sources / "only.md").write_text("only source text\n", encoding="utf-8")
    (curriculum / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "curriculum_manifest_v1",
                "sources": [
                    {
                        "id": "only_source",
                        "title": "Only Source",
                        "path": "sources/only.md",
                        "tags": [],
                        "license": "demo",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    raw_cases = [
        {"query": "one", "expect_source_ids": ["only_source"]},
        {"query": "two", "expect_source_ids": ["only_source"]},
    ]
    (curriculum / "retrieval_bench.json").write_text(
        json.dumps({"schema_version": "retrieval_bench@1", "cases": raw_cases}),
        encoding="utf-8",
    )

    bench_module = _load_bench_module()
    bench_module._REPO_ROOT = fake_repo

    problem = bench_module._validate_shipped_benchmark_contract(
        fake_repo / "curriculum" / "retrieval_bench.json",
        fake_repo / "curriculum",
        raw_cases,
        {"only_source"},
    )

    assert problem == "shipped benchmark is vacuous: expected sources collapse to a single source id"
