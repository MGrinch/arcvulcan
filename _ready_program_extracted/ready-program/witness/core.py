from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "witness_event@1"

SAFE_KEY_ALLOWLIST = {"session_report", "session_id", "turn_result", "knowledge_graph"}
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "secret",
    "auth",
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "cookie",
    "private_key",
    "ssn",
    "sin",
}
SENSITIVE_KEY_MARKERS = (
    "_password",
    "_passwd",
    "_secret",
    "_token",
    "_api_key",
    "_apikey",
    "_private_key",
)

SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[0-9A-Za-z]{20,}\b"),
)
MAX_SCRUB_DEPTH = 64
MAX_SCRUB_NODES = 100000
MAX_SCRUB_STRING_CHARS = 4096
MAX_EVENT_ID_JSON_BYTES = 2_000_000
_STABLE_CREATED_AT = "1970-01-01T00:00:00Z"
_VOLATILE_EVENT_ID_FIELDS = {
    "latency_ms",
    "duration_ms",
    "elapsed_ms",
    "wall_time_ms",
    "time_ms",
}
_VOLATILE_EVENT_ID_FIELD_SUFFIXES = (
    "_latency_ms",
    "_duration_ms",
    "_elapsed_ms",
    "_wall_time_ms",
    "_time_ms",
)


def _is_sensitive_key(key: Any) -> bool:
    k = str(key).strip().lower().replace("-", "_")
    if not k:
        return False
    if k in SAFE_KEY_ALLOWLIST:
        return False
    if k in SENSITIVE_KEYS:
        return True
    return any(k.endswith(marker) for marker in SENSITIVE_KEY_MARKERS)


def scrub_pii(obj: Any) -> Any:
    """Best-effort PII scrubbing for dict/list payloads."""
    budget = [MAX_SCRUB_NODES]
    seen_ids: set[int] = set()

    def _walk(value: Any, depth: int) -> Any:
        if budget[0] <= 0:
            return "<truncated>"
        budget[0] -= 1

        if depth > MAX_SCRUB_DEPTH:
            return "<truncated>"

        if isinstance(value, (dict, list, tuple, set)):
            oid = id(value)
            if oid in seen_ids:
                return "<cycle>"
            seen_ids.add(oid)

        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                safe_key = _utf8_safe_text(k)
                if _is_sensitive_key(safe_key):
                    out[safe_key] = "<redacted>"
                else:
                    out[safe_key] = _walk(v, depth + 1)
            seen_ids.discard(id(value))
            return out
        if isinstance(value, list):
            out_list = [_walk(x, depth + 1) for x in value]
            seen_ids.discard(id(value))
            return out_list
        if isinstance(value, tuple):
            out_tuple = [_walk(x, depth + 1) for x in value]
            seen_ids.discard(id(value))
            return out_tuple
        if isinstance(value, set):
            out_set = [_walk(x, depth + 1) for x in sorted(value, key=lambda x: repr(x))]
            seen_ids.discard(id(value))
            return out_set
        if isinstance(value, str):
            safe_value = _utf8_safe_text(value)
            too_long = len(safe_value) > MAX_SCRUB_STRING_CHARS
            out = safe_value[:MAX_SCRUB_STRING_CHARS] if too_long else safe_value
            for rx in SENSITIVE_VALUE_PATTERNS:
                out = rx.sub("<redacted>", out)
            if too_long:
                return out + "...<truncated>"
            return out
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace")
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return repr(value)

    return _walk(obj, 0)


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _determinism_enabled() -> bool:
    raw = os.environ.get("DAEDALUS_ENFORCE_DETERMINISM")
    if raw is None:
        return True
    s = raw.strip().lower()
    if not s:
        return True
    return s in {"1", "true", "yes", "on"}


def _json_fallback(v: Any):
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8", errors="replace")
    if isinstance(v, datetime):
        return v.isoformat()
    return repr(v)


def _utf8_safe_text(value: Any) -> str:
    return str(value or "").encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {_utf8_safe_text(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in sorted(value, key=lambda x: repr(x))]
    if isinstance(value, str):
        return _utf8_safe_text(value)
    if isinstance(value, Path):
        return _utf8_safe_text(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _utf8_safe_text(_json_fallback(value))


def _event_id_field_name(key: Any) -> str:
    return _utf8_safe_text(key).strip().lower().replace("-", "_")


def _is_event_id_volatile_field(key: Any) -> bool:
    name = _event_id_field_name(key)
    if not name:
        return False
    if name in _VOLATILE_EVENT_ID_FIELDS:
        return True
    return any(name.endswith(suffix) for suffix in _VOLATILE_EVENT_ID_FIELD_SUFFIXES)


def _normalize_event_id_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            safe_key = _utf8_safe_text(k)
            if _is_event_id_volatile_field(safe_key):
                out[safe_key] = f"<volatile:{_event_id_field_name(safe_key)}>"
            else:
                out[safe_key] = _normalize_event_id_payload(v)
        return out
    if isinstance(value, list):
        return [_normalize_event_id_payload(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize_event_id_payload(v) for v in value]
    if isinstance(value, set):
        return [_normalize_event_id_payload(v) for v in sorted(value, key=lambda x: repr(x))]
    return _json_safe(value)


def _event_id(issue_id: str, payload: dict) -> str:
    normalized_payload = _normalize_event_id_payload(payload)
    h = hashlib.sha256()
    h.update(issue_id.encode("utf-8"))
    enc = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_json_fallback)
    total = 0
    hashed = 0
    for chunk in enc.iterencode(normalized_payload):
        b = chunk.encode("utf-8", errors="replace")
        total += len(b)
        if hashed < MAX_EVENT_ID_JSON_BYTES:
            remaining = MAX_EVENT_ID_JSON_BYTES - hashed
            take = min(len(b), remaining)
            h.update(b[:take])
            hashed += take
    if total > MAX_EVENT_ID_JSON_BYTES:
        h.update(f"...len={total}".encode("utf-8"))
    return "EVT-" + h.hexdigest()[:12]


@dataclass(frozen=True)
class WitnessEvent:
    schema_version: str
    event_id: str
    issue_id: str
    created_at: str
    payload: dict


class WitnessCore:
    """Minimal crash-to-report core."""

    def make_event(self, issue_id: str, payload: dict, *, created_at: str | None = None) -> WitnessEvent:
        clean = _json_safe(scrub_pii(payload or {}))
        default_created_at = _STABLE_CREATED_AT if _determinism_enabled() else _utc_now_z()
        safe_issue_id = _utf8_safe_text(issue_id)
        safe_created_at = _utf8_safe_text(created_at or default_created_at)
        return WitnessEvent(
            schema_version=SCHEMA_VERSION,
            event_id=_event_id(safe_issue_id, clean),
            issue_id=safe_issue_id,
            created_at=safe_created_at,
            payload=clean,
        )

    def write_event_json(self, event: WitnessEvent, path: str) -> None:
        path_obj = Path(path)
        parent = path_obj.parent
        if str(parent):
            parent.mkdir(parents=True, exist_ok=True)
        doc = _json_safe({
            "schema_version": event.schema_version,
            "event_id": event.event_id,
            "issue_id": event.issue_id,
            "created_at": event.created_at,
            "payload": event.payload,
        })
        if path_obj.exists() and path_obj.is_symlink():
            raise RuntimeError("refusing to overwrite symlinked witness artifact")
        tmp_path = parent / f".{path_obj.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}"
        fd = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(str(tmp_path), flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                fd = None
                json.dump(doc, f, indent=2, sort_keys=True, ensure_ascii=False, default=_json_fallback)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(path_obj))
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
