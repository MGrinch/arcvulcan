"""Canonical JSON helpers for tools.

Every tool-produced *.json artifact should be byte-stable so that
`tools/artifact_roundtrip.py --strict` passes without rewriting.

Canonical form:
  - UTF-8
  - ensure_ascii=False
  - indent=2
  - sort_keys=True
  - trailing newline

Do NOT use this for network payloads (those sometimes require compact JSON).
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Union


def dumps_canonical(obj: Any) -> str:
    """Serialize object to canonical JSON text."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def _ensure_no_symlink_in_path(p: Path) -> None:
    # Refuse writes through symlinked targets/parents.
    if p.exists() and p.is_symlink():
        raise ValueError(f"refusing to write through symlink target: {p}")
    cur = p.parent
    while True:
        if cur.exists():
            if cur.is_symlink():
                raise ValueError(f"refusing to write through symlink parent: {cur}")
            break
        nxt = cur.parent
        if nxt == cur:
            break
        cur = nxt


def write_json(path: Union[str, Path], obj: Any) -> None:
    """Write canonical JSON to *path* (ensures parent dirs exist)."""
    p = Path(path)
    _ensure_no_symlink_in_path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.parent.is_symlink():
        raise ValueError(f"refusing to write inside symlink directory: {p.parent}")
    tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
    if tmp.exists() and tmp.is_symlink():
        raise ValueError(f"refusing to use symlink temp path: {tmp}")
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(tmp), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            fd = None
            f.write(dumps_canonical(obj))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
