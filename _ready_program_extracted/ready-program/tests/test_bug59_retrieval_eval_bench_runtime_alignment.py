from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _load_bench_module():
    spec = importlib.util.spec_from_file_location(
        "retrieval_eval_bench_under_test_bug59", REPO_ROOT / "tools" / "retrieval_eval_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_minimal_curriculum(repo_root: Path) -> None:
    curriculum = repo_root / "curriculum"
    sources = curriculum / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "a.md").write_text("alpha evidence\n", encoding="utf-8")
    (sources / "b.md").write_text("beta evidence\n", encoding="utf-8")
    (curriculum / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "curriculum_manifest_v1",
                "sources": [
                    {"id": "a", "title": "A", "path": "sources/a.md", "tags": [], "license": "demo"},
                    {"id": "b", "title": "B", "path": "sources/b.md", "tags": [], "license": "demo"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (curriculum / "retrieval_bench.json").write_text(
        json.dumps(
            {
                "schema_version": "retrieval_bench@1",
                "cases": [
                    {"query": "alpha", "expect_source_ids": ["a"]},
                    {"query": "beta", "expect_source_ids": ["b"]},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_default_paths_are_repo_anchored_not_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bench_module = _load_bench_module()
    run_dir = tmp_path / "run-success"

    def _allocate(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bench_module, "allocate_run_dir", _allocate)
    monkeypatch.setattr(sys, "argv", ["retrieval_eval_bench.py", "--issue", "ISSUE-20260314-059"])

    result = bench_module.main()

    assert result == 0
    report = json.loads((run_dir / "retrieval_eval_report.json").read_text(encoding="utf-8"))
    assert Path(report["bench_path"]) == REPO_ROOT / "curriculum" / "retrieval_bench.json"
    assert Path(report["grounding_dir"]) == REPO_ROOT / "curriculum"


def test_grounding_dir_resolution_rejects_absolute_and_escape_symlink(tmp_path: Path) -> None:
    bench_module = _load_bench_module()
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link_name = fake_repo / "curriculum_link"
    try:
        link_name.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    bench_module._REPO_ROOT = fake_repo

    assert bench_module._resolve_grounding_dir(str(outside)) is None
    assert bench_module._resolve_grounding_dir("curriculum_link") is None

    inside = fake_repo / "curriculum"
    inside.mkdir()
    assert bench_module._resolve_grounding_dir("curriculum") == inside.resolve()


def test_missing_bench_does_not_allocate_run_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bench_module = _load_bench_module()
    fake_repo = tmp_path / "repo"
    _write_minimal_curriculum(fake_repo)
    bench_module._REPO_ROOT = fake_repo

    def _unexpected_allocate(_run_id: str) -> Path:
        raise AssertionError("allocate_run_dir should not be called for invalid bench input")

    monkeypatch.setattr(bench_module, "allocate_run_dir", _unexpected_allocate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "retrieval_eval_bench.py",
            "--issue",
            "ISSUE-20260314-059",
            "--bench",
            "missing-bench.json",
        ],
    )

    result = bench_module.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "bench not found or empty" in captured.out


def test_invalid_grounding_dir_does_not_allocate_run_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bench_module = _load_bench_module()
    fake_repo = tmp_path / "repo"
    _write_minimal_curriculum(fake_repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    link_name = fake_repo / "curriculum_link"
    try:
        link_name.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    bench_module._REPO_ROOT = fake_repo

    def _unexpected_allocate(_run_id: str) -> Path:
        raise AssertionError("allocate_run_dir should not be called for invalid grounding input")

    monkeypatch.setattr(bench_module, "allocate_run_dir", _unexpected_allocate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "retrieval_eval_bench.py",
            "--issue",
            "ISSUE-20260314-059",
            "--grounding-dir",
            "curriculum_link",
        ],
    )

    result = bench_module.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "invalid grounding dir" in captured.out
