from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import backend_fault_injector as injector_mod


_SIDE_EFFECTS = {
    "stdout_present": False,
    "stdout_len": 0,
    "stderr_present": False,
    "stderr_len": 0,
}


def test_stock_scenarios_include_empty_fault_fallback_cases() -> None:
    scenarios = {entry["name"]: entry for entry in injector_mod._stock_scenarios()}

    assert "tutor_fault_empty_fallback" in scenarios
    assert scenarios["tutor_fault_empty_fallback"] == {
        "name": "tutor_fault_empty_fallback",
        "expect_raise": False,
        "env": {"DAEDALUS_TUTOR_BACKEND": "fault", "DAEDALUS_FAULT_MODE": "empty"},
        "expect_effective_backend": "stub",
        "require_backend_error": True,
    }

    assert "mirror_fault_empty_handled" in scenarios
    assert scenarios["mirror_fault_empty_handled"] == {
        "name": "mirror_fault_empty_handled",
        "expect_raise": False,
        "env": {
            "DAEDALUS_ENABLE_MIRROR": "1",
            "DAEDALUS_MIRROR_BACKEND": "fault",
            "DAEDALUS_FAULT_MODE": "empty",
        },
        "expect_effective_backend": "stub",
        "require_backend_error": True,
        "expect_mirror_prediction": False,
    }



def test_scenario_rejects_handled_fallback_without_effective_backend_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        injector_mod,
        "_capture_route_turn",
        lambda *args, **kwargs: (
            True,
            {
                "reply": "stub fallback reply",
                "backend_error": "handled backend error",
                "effective_backend": "fault",
                "requested_backend": "fault",
            },
            dict(_SIDE_EFFECTS),
        ),
    )

    out = injector_mod._scenario(
        "tutor_fault_exception_fallback",
        expect_raise=False,
        env={},
        expect_effective_backend="stub",
        require_backend_error=True,
    )

    assert out["pass"] is False
    assert "expected effective_backend='stub', got 'fault'" in out["details"]



def test_scenario_rejects_handled_fallback_without_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        injector_mod,
        "_capture_route_turn",
        lambda *args, **kwargs: (
            True,
            {
                "reply": "stub fallback reply",
                "backend_error": None,
                "effective_backend": "stub",
                "requested_backend": "fault",
            },
            dict(_SIDE_EFFECTS),
        ),
    )

    out = injector_mod._scenario(
        "tutor_fault_empty_fallback",
        expect_raise=False,
        env={},
        expect_effective_backend="stub",
        require_backend_error=True,
    )

    assert out["pass"] is False
    assert "expected backend_error on handled fallback" in out["details"]
