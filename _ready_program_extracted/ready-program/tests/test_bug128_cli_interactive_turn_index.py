from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xyzgl import cli


def test_interactive_cli_respects_resume_turn_index(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_route_turn(user_text: str, *, seed: int | None, cfg, turn_index: int):
        calls.append(turn_index)
        return {"input": user_text, "turn_index": turn_index}

    monkeypatch.setattr(cli, "route_turn", fake_route_turn)
    monkeypatch.setattr(sys, "argv", ["xyzgl", "--interactive", "--turn-index", "7", "--seed", "123"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("first turn\nsecond turn\nexit\n"))

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = cli.main()

    assert rc == 0
    assert calls == [7, 8]
    assert '"turn_index": 7' in captured.getvalue()
    assert '"turn_index": 8' in captured.getvalue()


def test_interactive_cli_rejects_negative_resume_turn_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["xyzgl", "--interactive", "--turn-index", "-1"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 2
