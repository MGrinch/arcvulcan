#!/usr/bin/env python3
"""Run directory allocation for Daedalus tools.

Goal: tools should still produce run bundles even if the repo directory is
read-only (e.g., installed as a package). Prefer ./runs when writable,
otherwise fall back to a temp directory.

Override:
  DAEDALUS_RUNS_DIR=/path/to/runs
  DAEDALUS_RUNS_DIR=relative/path  (resolved from the repository root)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

_RUNS_ROOT_CACHE: Path | None = None
_MAX_RUN_ID_JSON_BYTES = 2_000_000
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".__write_probe__"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _repo_anchored_path(value: str | os.PathLike[str]) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def invalid_runs_override_reason() -> str | None:
    env = os.getenv("DAEDALUS_RUNS_DIR")
    if env is None or str(env).strip() == "":
        return None
    p = _repo_anchored_path(env)
    if _is_writable_dir(p):
        return None
    return f"invalid DAEDALUS_RUNS_DIR override: {env} is not a writable directory"


def runs_root() -> Path:
    global _RUNS_ROOT_CACHE
    env = os.getenv("DAEDALUS_RUNS_DIR")
    if env:
        p = _repo_anchored_path(env)
        if _is_writable_dir(p):
            return p.resolve()
    repo_runs = _REPO_ROOT / "runs"
    if _is_writable_dir(repo_runs):
        return repo_runs.resolve()
    if _RUNS_ROOT_CACHE is not None and _is_writable_dir(_RUNS_ROOT_CACHE):
        return _RUNS_ROOT_CACHE.resolve()
    # Fallback to temp
    repo_hint = str(Path(__file__).resolve().parents[1])
    repo_hash = hashlib.sha256(repo_hint.encode("utf-8")).hexdigest()[:10]
    tmp_parent = Path(tempfile.gettempdir())
    try:
        tmp = Path(tempfile.mkdtemp(prefix=f"daedalus_runs_{repo_hash}_", dir=str(tmp_parent)))
    except Exception:
        tmp = tmp_parent / f"daedalus_runs_{repo_hash}"
        tmp.mkdir(parents=True, exist_ok=True)
    _RUNS_ROOT_CACHE = tmp
    return tmp


def _normalize_run_id(run_id: str) -> str:
    rid = (run_id or "").strip()
    if not rid:
        raise ValueError("run_id is required")
    p = Path(rid)
    if p.is_absolute():
        raise ValueError("run_id must be relative")
    if any(part in {"", ".", ".."} for part in p.parts):
        raise ValueError("run_id contains invalid path segments")
    safe = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in rid)
    if not safe:
        raise ValueError("run_id became empty after sanitization")
    return safe


def _normalize_for_id(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if isinstance(value, Path):
        return _normalize_for_id(str(value))
    if isinstance(value, dict):
        return {str(k): _normalize_for_id(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_id(v) for v in value]
    if isinstance(value, set):
        return [_normalize_for_id(v) for v in sorted(value, key=lambda x: repr(x))]
    return value


def make_run_id(*parts: Any) -> str:
    """Generate a run id.

    - With no arguments, preserves the legacy unpredictable timestamp/random id.
    - With one or more arguments, derives a stable id from canonicalized inputs.
    """
    if not parts:
        return f"{int(time.time() * 1000)}-{secrets.randbelow(1_000_000_000):09d}"

    normalized = _normalize_for_id(list(parts))
    enc = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    h = hashlib.sha256()
    total = 0
    hashed = 0
    for chunk in enc.iterencode(normalized):
        b = chunk.encode("utf-8", errors="replace")
        total += len(b)
        if hashed < _MAX_RUN_ID_JSON_BYTES:
            remaining = _MAX_RUN_ID_JSON_BYTES - hashed
            take = min(len(b), remaining)
            h.update(b[:take])
            hashed += take
    if total > _MAX_RUN_ID_JSON_BYTES:
        h.update(f"...len={total}".encode("utf-8"))

    prefix = str(parts[0] or "run").strip().lower() if parts else "run"
    prefix = "".join(ch if ch.isalnum() else "-" for ch in prefix).strip("-") or "run"
    return f"{prefix}-{h.hexdigest()[:16]}"


def allocated_run_id(run_dir: Path) -> str:
    """Return the final allocated run id from the on-disk directory name."""
    return _normalize_run_id(run_dir.name)


def allocate_run_dir(run_id: str) -> Path:
    root = runs_root().resolve()
    base = _normalize_run_id(run_id)
    candidate = root / base
    suffix = 1
    max_attempts = 10000
    while True:
        if suffix > max_attempts:
            raise RuntimeError("unable to allocate run dir after many attempts")
        try:
            candidate.resolve().relative_to(root)
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = root / f"{base}_{suffix}"
            suffix += 1
        except (ValueError, OSError):
            # Handle symlink escapes and transient filesystem errors as collisions.
            candidate = root / f"{base}_{suffix}"
            suffix += 1
