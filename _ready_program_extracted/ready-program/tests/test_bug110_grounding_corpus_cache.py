from __future__ import annotations

import json
from pathlib import Path

from xyzgl.grounding.corpus import MAX_SOURCES
from xyzgl.grounding.prompting import _CORPUS_CACHE, _corpus_signature, build_grounding


def _write_manifest(corpus_dir: Path, sources: list[dict]) -> None:
    (corpus_dir / "manifest.json").write_text(
        json.dumps({"sources": sources}, indent=2),
        encoding="utf-8",
    )


def test_build_grounding_invalidates_cache_after_source_edit_and_delete(tmp_path: Path) -> None:
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    source_path = sources_dir / "joint_fitup.md"
    source_path.write_text(
        "Root opening starts narrow.\n\nTravel speed stays moderate.\n",
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        [
            {
                "id": "fitup",
                "title": "Joint Fit-Up",
                "path": "sources/joint_fitup.md",
            }
        ],
    )

    _CORPUS_CACHE.clear()
    first_text, first_meta = build_grounding(tmp_path, "travel speed", max_snippets=1, max_chars=240)
    assert "Travel speed stays moderate." in first_text
    assert first_meta["snippets"]

    source_path.write_text(
        "Root opening was widened.\n\nArc length stays short.\n",
        encoding="utf-8",
    )
    second_text, second_meta = build_grounding(tmp_path, "arc length", max_snippets=1, max_chars=240)
    assert "Arc length stays short." in second_text
    assert "Travel speed stays moderate." not in second_text
    assert second_meta["snippets"]

    source_path.unlink()
    third_text, third_meta = build_grounding(tmp_path, "arc length", max_snippets=1, max_chars=240)
    assert third_text == ""
    assert third_meta["snippets"] == []


def test_corpus_signature_tracks_manifest_listed_sources_beyond_runtime_source_cap(tmp_path: Path) -> None:
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()

    manifest_sources: list[dict] = []
    for index in range(MAX_SOURCES + 1):
        rel_path = f"sources/source_{index:03d}.md"
        (tmp_path / rel_path).write_text(f"needle-{index}\n", encoding="utf-8")
        manifest_sources.append(
            {
                "id": f"source-{index:03d}",
                "title": f"Source {index:03d}",
                "path": rel_path,
            }
        )
    _write_manifest(tmp_path, manifest_sources)

    baseline = _corpus_signature(tmp_path)

    capped_out_path = tmp_path / manifest_sources[-1]["path"]
    capped_out_path.write_text("needle-updated\n", encoding="utf-8")

    refreshed = _corpus_signature(tmp_path)
    assert refreshed != baseline
