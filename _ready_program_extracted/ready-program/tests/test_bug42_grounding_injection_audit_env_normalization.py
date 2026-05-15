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


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "grounding_injection_audit_under_test_bug42",
        REPO_ROOT / "tools" / "grounding_injection_audit.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_repo_fixture(repo_root: Path) -> None:
    (repo_root / "STABLE").mkdir(parents=True, exist_ok=True)
    (repo_root / "STABLE" / "ROLE_PROTOCOL.md").write_text("protocol guidance\n", encoding="utf-8")
    sources_dir = repo_root / "curriculum" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "curriculum" / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "fixture",
                        "title": "Fixture Source",
                        "path": "sources/fixture.md",
                        "tags": [],
                        "license": "demo",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (sources_dir / "fixture.md").write_text("stable_anchor environment normalization proof\n", encoding="utf-8")


def test_invalid_absolute_grounding_dir_override_is_normalized_to_repo_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audit_module = _load_audit_module()
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    _write_repo_fixture(fake_repo)

    outside = tmp_path / "outside_curriculum"
    outside.mkdir()
    (outside / "manifest.json").write_text('{"sources": []}\n', encoding="utf-8")

    run_dir = tmp_path / "runs" / "grounding-audit"

    def _allocate(_run_id: str) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(audit_module, "_REPO_ROOT", fake_repo)
    monkeypatch.setattr(audit_module, "allocate_run_dir", _allocate)
    monkeypatch.setattr(audit_module, "_run_id", lambda: "grounding-audit")
    monkeypatch.setattr("xyzgl.prompting._repo_root", lambda: fake_repo)
    monkeypatch.setenv("DAEDALUS_GROUNDING_DIR", str(outside))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "grounding_injection_audit.py",
            "--issue",
            "ISSUE-20260321-042",
            "--text",
            "stable_anchor",
        ],
    )

    result = audit_module.main()

    assert result == 0
    report = json.loads((run_dir / "grounding_audit_report.json").read_text(encoding="utf-8"))
    assert report["pass"] is True
    assert report["requested_grounding_dir"] == str(outside)
    assert report["grounding_dir"] == "curriculum"
    assert Path(report["grounding_dir_abs"]) == (fake_repo / "curriculum").resolve()
    assert report["notes"] == [
        f"invalid grounding_dir override ignored: {str(outside)!r}; using 'curriculum'"
    ]
