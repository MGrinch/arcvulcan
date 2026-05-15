from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import backend_contract_probe as probe_mod


def test_main_rejects_empty_backend_selection_before_run_dir_allocation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_allocate_run_dir(*args, **kwargs):  # pragma: no cover - should never be reached
        raise AssertionError("allocate_run_dir should not run when no backends are selected")

    def fail_probe_one(*args, **kwargs):  # pragma: no cover - should never be reached
        raise AssertionError("_probe_one should not run when no backends are selected")

    monkeypatch.setattr(probe_mod, "validate_issue_id", lambda issue: None)
    monkeypatch.setattr(probe_mod, "allocate_run_dir", fail_allocate_run_dir)
    monkeypatch.setattr(probe_mod, "_probe_one", fail_probe_one)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backend_contract_probe",
            "--issue",
            "ISSUE-20260319-056",
            "--tutor-backends",
            "",
            "--mirror-backends",
            "",
        ],
    )

    exit_code = probe_mod.main()

    assert exit_code == 2
    out = capsys.readouterr().out
    assert out.strip() == "INCOMPLETE: no backends selected; specify at least one tutor or mirror backend"
