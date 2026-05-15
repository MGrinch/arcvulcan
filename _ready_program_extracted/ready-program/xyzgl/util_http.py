from __future__ import annotations

import json
import os
import ssl
import socket
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_REQUEST_BYTES = 5_000_000
MAX_RESPONSE_PREVIEW_CHARS = 240
MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S = 120.0
MIN_AUTH_INTERVAL_S_DEFAULT = 0.25
_FORBIDDEN_REQUEST_HEADERS = {"host", "content-length", "transfer-encoding"}

_AUTH_THROTTLE_LOCK = threading.Lock()
_LAST_AUTH_POST_BY_HOST: dict[str, float] = {}


class HTTPError(RuntimeError):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _ = (req, fp, msg, headers, newurl)
        raise HTTPError(f"redirect blocked ({code})")


def _validate_post_url(url: str) -> None:
    try:
        u = urlsplit(url or "")
    except Exception:
        raise HTTPError(f"Invalid URL: {url!r}")
    if u.scheme not in {"http", "https"}:
        raise HTTPError(f"Unsupported URL scheme: {u.scheme!r}")
    if not (u.hostname or "").strip():
        raise HTTPError("URL must include a hostname")
    if (u.username is not None) or (u.password is not None):
        raise HTTPError("URL must not include credentials")
    try:
        port = u.port
    except ValueError as e:
        raise HTTPError(f"Invalid URL port: {e}") from e
    if port is not None and not (1 <= int(port) <= 65535):
        raise HTTPError("URL port out of range")


def _read_limited(resp, *, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        raise HTTPError("max_bytes must be > 0")
    buf = bytearray()
    total = 0
    while True:
        chunk = resp.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPError(f"HTTP response exceeded max_bytes={max_bytes}")
        buf.extend(chunk)
    return bytes(buf)


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise HTTPError(f"duplicate JSON key in response: {k!r}")
        out[k] = v
    return out


def _decode_response_text(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _validate_header_fields(headers: dict | None) -> None:
    if not headers:
        return
    for k, v in headers.items():
        ks = str(k or "")
        vs = str(v or "")
        if ("\r" in ks) or ("\n" in ks) or ("\r" in vs) or ("\n" in vs):
            raise HTTPError("invalid header contains control characters")
        if ks.strip().lower() in _FORBIDDEN_REQUEST_HEADERS:
            raise HTTPError(f"forbidden header override: {ks!r}")


def _auth_header_present(headers: dict | None) -> bool:
    if not headers:
        return False
    for k in headers:
        if str(k or "").strip().lower() == "authorization":
            return True
    return False


def _auth_min_interval_s() -> float:
    raw = os.getenv("DAEDALUS_AUTH_MIN_INTERVAL_MS", "").strip()
    if not raw:
        return MIN_AUTH_INTERVAL_S_DEFAULT
    try:
        ms = int(raw)
    except Exception:
        return MIN_AUTH_INTERVAL_S_DEFAULT
    if ms < 0:
        return 0.0
    return min(ms / 1000.0, 5.0)


def _throttle_auth_requests(url: str, headers: dict | None) -> None:
    if not _auth_header_present(headers):
        return
    interval = _auth_min_interval_s()
    if interval <= 0:
        return
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        host = ""
    if not host:
        return
    now = time.monotonic()
    sleep_s = 0.0
    with _AUTH_THROTTLE_LOCK:
        last = _LAST_AUTH_POST_BY_HOST.get(host)
        if last is not None:
            delta = now - last
            if delta < interval:
                sleep_s = interval - delta
        _LAST_AUTH_POST_BY_HOST[host] = now + sleep_s
    if sleep_s > 0:
        time.sleep(sleep_s)


def post_json(
    url: str,
    payload: dict,
    *,
    timeout_s: float = 30.0,
    headers: dict | None = None,
    max_response_bytes: int = 5_000_000,
    max_request_bytes: int = MAX_REQUEST_BYTES,
) -> tuple[dict, int]:
    """POST JSON and return (response_json, latency_ms).

    Uses stdlib only (no external deps). Raises HTTPError on failure.
    """
    _validate_post_url(url)
    if not isinstance(payload, dict):
        raise HTTPError("payload must be a JSON object")
    if max_request_bytes <= 0:
        raise HTTPError("max_request_bytes must be > 0")
    if max_response_bytes <= 0:
        raise HTTPError("max_response_bytes must be > 0")
    _validate_header_fields(headers)
    try:
        timeout_s = float(timeout_s)
    except Exception:
        timeout_s = 30.0
    timeout_s = max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, timeout_s))
    _throttle_auth_requests(url, headers)

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > max_request_bytes:
        raise HTTPError(f"HTTP request exceeded max_request_bytes={max_request_bytes}")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    u = urlsplit(url)
    ssl_ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(_NoRedirectHandler(), urllib.request.HTTPSHandler(context=ssl_ctx))
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=timeout_s) as resp:
            final_u = urlsplit(str(resp.geturl() or url))
            if final_u.scheme != u.scheme or final_u.hostname != u.hostname:
                raise HTTPError("redirected to unexpected host/scheme")
            content_type = str(resp.headers.get("Content-Type") or "").lower()
            if content_type and "json" not in content_type:
                raise HTTPError(f"Unexpected Content-Type from {url}: {content_type!r}")
            raw_bytes = _read_limited(resp, max_bytes=max_response_bytes)
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as e:
        raise HTTPError(f"HTTP POST failed: {url} -> {e}") from e

    dt_ms = int((time.monotonic() - t0) * 1000)
    try:
        text = _decode_response_text(raw_bytes)
        if not text.strip():
            raise HTTPError(f"Empty response body from {url}")
        parsed = json.loads(text, object_pairs_hook=_no_duplicate_pairs)
        if not isinstance(parsed, dict):
            raise HTTPError(f"Expected JSON object response from {url}, got {type(parsed).__name__}")
        return parsed, dt_ms
    except (UnicodeDecodeError, ValueError, TypeError) as e:
        preview = _decode_response_text(raw_bytes)[:MAX_RESPONSE_PREVIEW_CHARS].replace("\n", "\\n")
        raise HTTPError(f"Invalid JSON response from {url}: {e}; preview={preview!r}") from e
