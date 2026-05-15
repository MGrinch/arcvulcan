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

import backend_contract_probe as probe_mod


def test_fault_mode_expects_raise_treats_slow_as_supported_non_raising() -> None:
    assert probe_mod._fault_mode_expects_raise("slow") is False


def test_main_passes_non_raising_expectation_for_fault_backends_in_slow_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_calls: list[dict] = []
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    def fake_probe_one(observed_role: str, observed_backend_name: str, **kwargs):
        captured_calls.append(
            {
                "role": observed_role,
                "backend_name": observed_backend_name,
                "expected_raise": kwargs["expected_raise"],
                "allow_network": kwargs["allow_network"],
                "seed": kwargs["seed"],
                "cfg": kwargs["cfg"],
            }
        )
        return {"role": observed_role, "backend": observed_backend_name, "status": "PASS"}

    monkeypatch.setenv("DAEDALUS_FAULT_MODE", "slow")
    monkeypatch.setattr(probe_mod, "_probe_one", fake_probe_one)
    monkeypatch.setattr(probe_mod, "validate_issue_id", lambda issue: None)
    monkeypatch.setattr(probe_mod, "_run_id", lambda: "run-slow-fault")
    monkeypatch.setattr(probe_mod, "allocate_run_dir", lambda run_id: run_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backend_contract_probe",
            "--issue",
            "ISSUE-20260318-039",
            "--seed",
            "7",
            "--include-fault",
            "--tutor-backends",
            "",
            "--mirror-backends",
            "",
        ],
    )

    exit_code = probe_mod.main()

    assert exit_code == 0
    assert [(call["role"], call["backend_name"]) for call in captured_calls] == [
        ("tutor", "fault"),
        ("mirror", "fault"),
    ]

    tutor_call, mirror_call = captured_calls
    assert tutor_call["expected_raise"] is False
    assert tutor_call["allow_network"] is False
    assert tutor_call["seed"] == 7
    assert tutor_call["cfg"].tutor_backend == "fault"
    assert tutor_call["cfg"].enable_mirror is False

    assert mirror_call["expected_raise"] is False
    assert mirror_call["allow_network"] is False
    assert mirror_call["seed"] == 7
    assert mirror_call["cfg"].mirror_backend == "fault"
    assert mirror_call["cfg"].enable_mirror is True
