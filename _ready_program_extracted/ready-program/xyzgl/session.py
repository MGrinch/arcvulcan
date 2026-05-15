from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4


def _validated_turn_index(turn_index: int) -> int:
    turn_index = int(turn_index)
    if turn_index < 0:
        raise ValueError("turn_index must be >= 0")
    return turn_index


@dataclass(frozen=True)
class SessionState:
    """Lightweight session state for multi-turn runs."""

    session_id: str
    turn_index: int = 0

    @staticmethod
    def new(*, turn_index: int = 0) -> "SessionState":
        return SessionState(session_id=str(uuid4()), turn_index=_validated_turn_index(turn_index))

    def next_turn(self) -> "SessionState":
        return replace(self, turn_index=_validated_turn_index(self.turn_index + 1))
