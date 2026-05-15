from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from issue_id import validate_issue_id

_TOOL_MODULES = [
    "backend_fault_injector",
    "curriculum_corpus_linter",
    "grounding_injection_audit",
    "latency_cost_budget_enforcer",
    "repro_backends_smoke",
    "repro_grounding_protocol_smoke",
]


@pytest.mark.parametrize(
    ("issue_id", "expected_fragment"),
    [
        ("not-an-issue", "expected ^ISSUE-\\d{8}-\\d{3}$"),
        ("ISSUE-20260231-001", "expected real YYYYMMDD calendar date"),
    ],
)
def test_validate_issue_id_rejects_bad_shape_and_impossible_dates(
    issue_id: str,
    expected_fragment: str,
) -> None:
    err = validate_issue_id(issue_id)
    assert err is not None
    assert expected_fragment in err


@pytest.mark.parametrize("module_name", _TOOL_MODULES)
@pytest.mark.parametrize(
    "bad_issue",
    [
        "not-an-issue",
        "ISSUE-20260231-001",
    ],
)
def test_backend_validation_tools_reject_invalid_issue_before_side_effects(
    module_name: str,
    bad_issue: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module(module_name)

    def fail_run_dir(*args, **kwargs):  # pragma: no cover - should never be reached
        raise AssertionError(f"{module_name} should reject invalid --issue before allocating a run dir")

    monkeypatch.setattr(module, "allocate_run_dir", fail_run_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [module_name, "--issue", bad_issue],
    )

    exit_code = module.main()

    assert exit_code == 2
    out = capsys.readouterr().out
    assert out.startswith("INCOMPLETE: ")
    assert "--issue" in out
