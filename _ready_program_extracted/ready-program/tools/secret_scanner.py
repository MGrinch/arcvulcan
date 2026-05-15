#!/usr/bin/env python3
from __future__ import annotations

"""Lightweight secret scanner.

This is a dependency-free safety net similar in spirit to `trufflehog`.
It scans repository text files for common high-risk patterns:
  - Google API keys (AIza...)
  - OpenAI-style keys (sk-...)
  - private key blocks
  - generic `...TOKEN=...` hardcodes

This tool does *not* attempt to be perfect.

Exit codes:
  0 PASS
  1 FAIL
  2 INCOMPLETE
"""

import argparse
import hashlib
import os
import random
import re
import sys
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from issue_id import validate_issue_id
from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MAX_FILES = 20000
_DEFAULT_MAX_BYTES = 100 * 1024 * 1024
_BINARY_SNIFF_BYTES = 8192
_TRUNCATION_GAP_MARKER = "\n<...secret-scan-gap...>\n"


def _run_id() -> str:
    return make_run_id()


_DEFAULT_EXCLUDES = {
    "runs",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
}


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    ("openai_api_key", re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z\-_]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |)PRIVATE KEY-----")),
    ("github_pat", re.compile(r"\bghp_[0-9A-Za-z]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("npm_token", re.compile(r"\bnpm_[0-9A-Za-z]{24,}\b")),
    ("sendgrid_api_key", re.compile(r"\bSG\.[0-9A-Za-z_-]{16,}\.[0-9A-Za-z_-]{16,}\b")),
    ("slack_token", re.compile(r"\bxox(?:a|b|c|o|p|r|s|x)-[0-9A-Za-z-]{10,}\b")),
    ("azure_sas_token", re.compile(r"(?i)\bsv=\d{4}-\d{2}-\d{2}[^\s'\"]*?\bsig=[0-9A-Za-z%/+._=-]{16,}")),
    (
        "generic_token_assign",
        re.compile(r"(?i)\b(?:token|apikey|api_key|secret)\s*[:=]\s*['\"]?[0-9A-Za-z\-_=]{16,}"),
    ),
    (
        "password_assign",
        re.compile(r"(?i)\b(?:password|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
    (
        "bearer_literal",
        re.compile(r"(?i)\bauthorization\s*[:=]\s*['\"]?bearer\s+[0-9A-Za-z/+._=-]{16,}"),
    ),
    (
        "credential_url",
        re.compile(
            r"(?i)\b(?:svn\+ssh|scp|git|irc|xmpp|postgresql\+psycopg2|mysql\+pymysql|redis\+sentinel)://[^/\s:@]+:[^@/\s]{3,}@[^\s]+"
        ),
    ),
]



def _is_text(path: Path) -> bool:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".rar", ".pdf"}:
        return False
    try:
        with path.open("rb") as fh:
            chunk = fh.read(_BINARY_SNIFF_BYTES)
    except Exception:
        return False
    if not chunk:
        return True
    if b"\x00" in chunk:
        return False
    text_like = sum(1 for b in chunk if b in b"\t\n\r\f\b" or 32 <= b <= 126)
    return (text_like / len(chunk)) >= 0.85



def _is_within(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _iter_repo_files(root: Path):
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(dirpath)

        kept_dirs: list[str] = []
        for d in dirnames:
            dp = base / d
            if dp.is_symlink():
                continue
            try:
                rp = dp.resolve()
                rp.relative_to(root_resolved)
            except Exception:
                continue
            rel_parts = rp.relative_to(root_resolved).parts
            if rel_parts and rel_parts[0] in _DEFAULT_EXCLUDES:
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fn in filenames:
            fp = base / fn
            if fp.is_symlink():
                continue
            try:
                rp = fp.resolve()
                rp.relative_to(root_resolved)
            except Exception:
                continue
            yield rp

def _is_placeholder_match(token: str, snippet: str) -> bool:
    t = (token or "").lower()
    s = (snippet or "").lower()
    if "your_api_key" in t or "your_api_key" in s:
        return True
    if "<redacted>" in t or "<redacted>" in s:
        return True
    if (
        "example" in s
        or "dummy" in s
        or "test_key" in s
        or "placeholder" in s
        or "fixture" in s
        or "docs only" in s
        or "documentation" in s
        or "sample" in s
    ):
        return True
    return False



def _match_context(text: str, start: int, end: int, radius: int = 160) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]



_ASSIGNMENT_RE = re.compile(r"(?im)^\s*(?:export\s+)?([A-Za-z][A-Za-z0-9_-]{0,95})\s*[:=]\s*([^\r\n]+?)(?:\r)?$")
_KEY_LABEL_CONTEXTS = (
    "access",
    "account",
    "api",
    "app",
    "auth",
    "aws",
    "bearer",
    "bot",
    "client",
    "consumer",
    "jwt",
    "oauth",
    "private",
    "service",
    "session",
    "signing",
    "twilio",
    "webhook",
)
_PLACEHOLDER_VALUES = {
    "<redacted>",
    "changeme",
    "dummy",
    "example",
    "false",
    "none",
    "null",
    "placeholder",
    "sample",
    "true",
    "undefined",
    "your_api_key",
}



def _normalize_label(label: str) -> str:
    return "".join(ch.lower() for ch in (label or "") if ch.isalnum())



def _is_sensitive_assignment_label(label: str) -> bool:
    norm = _normalize_label(label)
    if not norm:
        return False
    if any(term in norm for term in ("token", "secret", "password", "passwd")):
        return True
    if norm.endswith("key") and any(ctx in norm for ctx in _KEY_LABEL_CONTEXTS):
        return True
    return False



def _clean_assignment_value(raw: str) -> str:
    value = (raw or "").strip()
    value = re.sub(r"\s+(?:#|//|;)\s.*$", "", value).strip()
    value = value.rstrip(",;").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value



def _looks_like_assignment_secret(label: str, raw_value: str) -> bool:
    value = _clean_assignment_value(raw_value)
    if not value:
        return False
    low = value.lower()
    if low in _PLACEHOLDER_VALUES:
        return False
    if "example" in low or "placeholder" in low or "dummy" in low:
        return False
    if low.startswith(("${", "$(", "<")):
        return False
    if low.startswith(("http://", "https://")):
        return False
    if low.startswith("bearer "):
        value = value[7:].strip()
        low = value.lower()
    if not value or any(ch.isspace() for ch in value):
        return False
    norm = _normalize_label(label)
    min_len = 8 if ("password" in norm or "passwd" in norm) else 12
    if len(value) < min_len:
        return False
    if re.fullmatch(r"[A-Za-z]+", value):
        return False
    if not re.fullmatch(r"[0-9A-Za-z/+._=%:-]+", value):
        return False
    return True



def _iter_assignment_hits(text: str):
    for m in _ASSIGNMENT_RE.finditer(text):
        label = m.group(1)
        raw_value = m.group(2)
        if not _is_sensitive_assignment_label(label):
            continue
        if not _looks_like_assignment_secret(label, raw_value):
            continue
        value = _clean_assignment_value(raw_value)
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        yield "assignment_secret", value, m.start(2), m.end(2)



def _read_scan_window(path: Path, *, max_bytes: int | None = None) -> tuple[str, bool, int]:
    try:
        file_size = int(path.stat().st_size)
    except Exception:
        return "", False, 0

    if max_bytes is not None:
        max_bytes = max(0, int(max_bytes))

    try:
        if max_bytes is None or file_size <= max_bytes:
            data = path.read_bytes()
            return data.decode("utf-8", errors="replace"), False, len(data)

        if max_bytes == 0:
            return "", True, 0

        head_bytes = max(1, max_bytes // 2)
        tail_bytes = max(0, max_bytes - head_bytes)
        with path.open("rb") as fh:
            head = fh.read(head_bytes)
            tail = b""
            if tail_bytes > 0:
                fh.seek(max(0, file_size - tail_bytes))
                tail = fh.read(tail_bytes)

        text = head.decode("utf-8", errors="replace")
        bytes_read = len(head)
        if tail:
            if file_size > len(head) + len(tail):
                text += _TRUNCATION_GAP_MARKER
            elif text and not text.endswith(("\n", "\r")):
                text += "\n"
            text += tail.decode("utf-8", errors="replace")
            bytes_read += len(tail)
        return text, True, bytes_read
    except Exception:
        return "", False, 0


def _scan_file(path: Path, *, max_bytes: int | None = None) -> tuple[list[dict], bool, int]:
    hits: list[dict] = []
    seen: set[tuple[str, str]] = set()
    text, truncated, bytes_read = _read_scan_window(path, max_bytes=max_bytes)
    if not text and bytes_read == 0:
        return hits, truncated, bytes_read

    def _append_hit(name: str, token: str, start: int, end: int) -> bool:
        token_hash = hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()[:12]
        key = (name, token_hash)
        if key in seen:
            return False
        snippet = _match_context(text, start, end)
        if _is_placeholder_match(token, snippet):
            return False
        seen.add(key)
        hits.append({"pattern": name, "match": f"<redacted:{token_hash}>", "snippet": "<context_redacted>"})
        return True

    for name, pat in _PATTERNS:
        for m in pat.finditer(text):
            _append_hit(name, m.group(0), m.start(), m.end())
            if len(hits) >= 20:
                return hits, truncated, bytes_read

    for name, token, start, end in _iter_assignment_hits(text):
        _append_hit(name, token, start, end)
        if len(hits) >= 20:
            return hits, truncated, bytes_read
    return hits, truncated, bytes_read



def main() -> int:
    ap = argparse.ArgumentParser(prog="secret_scanner")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--path", default=str(_REPO_ROOT), help="Repo root to scan")
    ap.add_argument("--enforce", action="store_true", help="Fail on any hit")
    ap.add_argument(
        "--allow-external-path",
        action="store_true",
        help="Allow scanning outside repository root (disabled by default).",
    )
    ap.add_argument("--max-files", type=int, default=_DEFAULT_MAX_FILES, help="Max files to scan before INCOMPLETE")
    ap.add_argument("--max-bytes", type=int, default=_DEFAULT_MAX_BYTES, help="Max total bytes to scan before INCOMPLETE")
    args = ap.parse_args()

    err = validate_issue_id(args.issue)
    if err:
        print(f"INCOMPLETE: {err}")
        return 2

    random.seed(1337)
    run_id = _run_id()
    run_dir = allocate_run_dir(run_id)
    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"INCOMPLETE: invalid --path: {root}")
        return 2
    if not args.allow_external_path and not _is_within(_REPO_ROOT.resolve(), root):
        print("INCOMPLETE: --path must be within repo root unless --allow-external-path is set")
        return 2

    hits: list[dict] = []
    scanned_files = 0
    scanned_bytes = 0
    truncated_reason: str | None = None
    partial_scan_files: list[dict[str, int | str]] = []

    for rp in _iter_repo_files(root):
        if not _is_within(root, rp):
            continue
        rel_parts = rp.relative_to(root).parts
        if rel_parts and rel_parts[0] in _DEFAULT_EXCLUDES:
            continue
        if not _is_text(rp):
            continue

        try:
            size = int(rp.stat().st_size)
        except Exception:
            continue

        if scanned_files >= int(args.max_files):
            truncated_reason = f"max files reached ({args.max_files})"
            break

        remaining_bytes = max(0, int(args.max_bytes) - scanned_bytes)
        if remaining_bytes <= 0:
            truncated_reason = f"max bytes reached ({args.max_bytes})"
            break

        scanned_files += 1
        scan_cap = size if size <= remaining_bytes else remaining_bytes
        file_hits, file_truncated, bytes_read = _scan_file(rp, max_bytes=scan_cap)
        scanned_bytes += bytes_read

        if file_hits:
            hits.append({"file": str(rp.relative_to(root)), "hits": file_hits})
            if len(hits) >= 50:
                break

        if file_truncated:
            partial_scan_files.append(
                {
                    "file": str(rp.relative_to(root)),
                    "file_size": size,
                    "scanned_bytes": bytes_read,
                    "reason": f"max bytes reached ({args.max_bytes})",
                }
            )
            truncated_reason = f"max bytes reached ({args.max_bytes})"
            break

    if truncated_reason:
        overall = "INCOMPLETE"
    else:
        overall = "PASS" if not hits else ("FAIL" if args.enforce else "PASS")

    report = {
        "schema_version": "secret_scan_report@1",
        "run_id": run_id,
        "issue_id": args.issue,
        "overall": overall,
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "hit_count": len(hits),
        "hits": hits,
        "enforced": bool(args.enforce),
        "limits": {"max_files": int(args.max_files), "max_bytes": int(args.max_bytes)},
        "partial_scan_files": partial_scan_files,
        "truncated_reason": truncated_reason,
    }
    write_json((run_dir / "secret_scan_report.json"), report)

    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": args.issue,
            "seed": 1337,
            "deterministic": False,
            "outputs": ["secret_scan_report.json", "secret_scan_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    (run_dir / "secret_scan_summary.md").write_text(
        "\n".join(
            [
                f"# Secret Scan Summary - {overall}",
                "",
                f"- issue: {args.issue}",
                f"- run_id: {run_id}",
                f"- scanned_files: {scanned_files}",
                f"- scanned_bytes: {scanned_bytes}",
                f"- hit_count: {len(hits)}",
                f"- enforced: {bool(args.enforce)}",
                f"- partial_scan_files: {len(partial_scan_files)}",
                f"- truncated_reason: {truncated_reason or 'none'}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"{overall}: wrote outputs to {run_dir}")
    if overall == "INCOMPLETE":
        return 2
    return 1 if (args.enforce and hits) else 0


if __name__ == "__main__":
    raise SystemExit(main())
