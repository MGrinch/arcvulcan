#!/usr/bin/env python3
"""Apply Signal Fidelity overlay (offline, no-overwrite).

Default source is the shipped extracted overlay directory:
  signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/

You may still pass:
  --overlay <path/to/overlay.zip>   (pure Python)
  --overlay <path/to/overlay_dir>   (copy)
  --overlay <path/to/overlay.rar>   (requires --allow-external-rar)

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

SHIPPED_DEFAULT = _REPO_ROOT / "signal_fidelity_src" / "XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED"
OUT_ROOT = _REPO_ROOT / "signal_fidelity_src"
SUBPROCESS_TIMEOUT_S = 120
MAX_SUBPROCESS_LOG_BYTES = 64 * 1024
MAX_ZIP_FILES = 5000
MAX_ZIP_TOTAL_BYTES = 500 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_EXTRACTED_FILES = 20000
MAX_EXTRACTED_TOTAL_BYTES = 800 * 1024 * 1024
MAX_SUBPROCESS_ARG_CHARS = 4096
_SAFE_ARG_RE = re.compile(r"^[^\x00\r\n]*$")


def _run_id(seed: int) -> str:
    _ = seed
    return make_run_id()


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(_REPO_ROOT))
    except Exception:
        return str(p)


def _trusted_binary(path: str) -> bool:
    try:
        p = Path(path).resolve()
    except Exception:
        return False
    try:
        p.relative_to(_REPO_ROOT.resolve())
        return False
    except Exception:
        pass

    roots: list[Path] = []
    for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        val = os.getenv(key)
        if val:
            roots.append(Path(val).resolve())
    for unix_root in ("/usr/bin", "/usr/local/bin", "/bin", "/opt/homebrew/bin"):
        roots.append(Path(unix_root))

    for root in roots:
        try:
            p.relative_to(root)
            return True
        except Exception:
            continue
    return False


def _tail_file_text(path: Path, *, max_bytes: int) -> str:
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start, os.SEEK_SET)
        data = f.read(max_bytes)
    text = data.decode("utf-8", errors="replace")
    return ("..." + text) if size > max_bytes else text


def _is_safe_subprocess_arg(arg: object) -> bool:
    s = str(arg or "")
    if not s:
        return False
    if len(s) > MAX_SUBPROCESS_ARG_CHARS:
        return False
    return bool(_SAFE_ARG_RE.fullmatch(s))


def _run(cmd: list[str], *, run_dir: Path) -> tuple[int, str]:
    if not cmd or not all(_is_safe_subprocess_arg(a) for a in cmd):
        return 1, "unsafe subprocess command arguments rejected"
    log_file = run_dir / f".overlay_extract_{os.getpid()}_{secrets.token_hex(6)}.log"
    try:
        with log_file.open("xb") as logf:
            proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
            try:
                rc = int(proc.wait(timeout=SUBPROCESS_TIMEOUT_S))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                out = _tail_file_text(log_file, max_bytes=MAX_SUBPROCESS_LOG_BYTES)
                return 1, f"command timed out after {SUBPROCESS_TIMEOUT_S}s: {' '.join(cmd)}\n{out}"
        return rc, _tail_file_text(log_file, max_bytes=MAX_SUBPROCESS_LOG_BYTES)
    except Exception as e:
        return 1, f"command failed: {' '.join(cmd)} | {type(e).__name__}: {e}"
    finally:
        if log_file.exists():
            try:
                log_file.unlink()
            except OSError:
                pass


def _pick_extractor() -> tuple[str, str] | None:
    for c in ("7z", "unrar", "bsdtar", "unar"):
        exe = shutil.which(c)
        if not exe:
            continue
        if not _trusted_binary(exe):
            continue
        return c, exe
    return None


def _extract_rar(extractor: str, extractor_exe: str, archive: Path, tmp: Path, *, run_dir: Path) -> tuple[int, str]:
    tmp.mkdir(parents=True, exist_ok=True)
    if extractor == "7z":
        return _run([extractor_exe, "x", str(archive), f"-o{tmp}", "-y"], run_dir=run_dir)
    if extractor == "unrar":
        return _run([extractor_exe, "x", "-o-", str(archive), str(tmp)], run_dir=run_dir)
    if extractor == "bsdtar":
        return _run([extractor_exe, "-xf", str(archive), "-C", str(tmp)], run_dir=run_dir)
    if extractor == "unar":
        return _run([extractor_exe, "-o", str(tmp), str(archive)], run_dir=run_dir)
    return 1, "unknown extractor"


def _iter_files(root: Path):
    for p in root.rglob("*"):
        try:
            st = p.lstat()
        except Exception:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        # Reject hardlinks to avoid copying aliased content unexpectedly.
        if getattr(st, "st_nlink", 1) > 1:
            continue
        yield p


def _validate_extracted_tree(root: Path) -> None:
    root_resolved = root.resolve()
    file_count = 0
    total_bytes = 0
    for p in root.rglob("*"):
        if p.is_symlink():
            raise ValueError(f"overlay contains symlink: {p}")
        try:
            p.resolve().relative_to(root_resolved)
        except Exception as e:
            raise ValueError(f"overlay path escaped extraction root: {p}") from e
        if p.is_file():
            file_count += 1
            total_bytes += int(p.stat().st_size)
            if file_count > MAX_EXTRACTED_FILES:
                raise ValueError(f"overlay extracted too many files: {file_count} > {MAX_EXTRACTED_FILES}")
            if total_bytes > MAX_EXTRACTED_TOTAL_BYTES:
                raise ValueError(
                    f"overlay extracted too many bytes: {total_bytes} > {MAX_EXTRACTED_TOTAL_BYTES}"
                )


def _safe_extract_zip(src_zip: Path, dst_root: Path) -> tuple[int, int]:
    dst_resolved = dst_root.resolve()
    extracted = 0
    total_uncompressed = 0
    with zipfile.ZipFile(src_zip, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_FILES:
            raise ValueError(f"zip has too many entries: {len(infos)} > {MAX_ZIP_FILES}")
        for info in infos:
            name = info.filename
            if not name or name.endswith("/"):
                continue
            total_uncompressed += int(info.file_size)
            if total_uncompressed > MAX_ZIP_TOTAL_BYTES:
                raise ValueError("zip exceeds uncompressed size limit")
            if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_COMPRESSION_RATIO:
                raise ValueError("zip entry exceeds compression ratio limit")
            mode = (info.external_attr >> 16) & 0xF000
            if mode == 0xA000:
                raise ValueError(f"zip contains symlink entry: {name}")

            rel = Path(name)
            if rel.is_absolute():
                raise ValueError(f"zip contains absolute path: {name}")
            target = (dst_resolved / rel).resolve()
            try:
                target.relative_to(dst_resolved)
            except Exception as e:
                raise ValueError(f"unsafe zip member path: {name}") from e

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as rf, open(target, "wb") as wf:
                shutil.copyfileobj(rf, wf)
            extracted += 1
    return extracted, total_uncompressed


def _copy_no_overwrite(src_root: Path, dst_root: Path) -> tuple[int, int]:
    copied = skipped = 0
    for src in _iter_files(src_root):
        if src.is_symlink():
            skipped += 1
            continue
        dst = dst_root / src.relative_to(src_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with src.open("rb") as rf, dst.open("xb") as wf:
                shutil.copyfileobj(rf, wf)
            shutil.copystat(src, dst)
            copied += 1
        except FileExistsError:
            skipped += 1
    return copied, skipped


def _count_regular_files(root: Path) -> int:
    return sum(1 for _ in _iter_files(root))


def main() -> int:
    ap = argparse.ArgumentParser(prog="apply_signal_fidelity_overlay")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--overlay", help="optional: .zip or directory (avoids RAR extractors)")
    ap.add_argument(
        "--from-src",
        action="store_true",
        help="Use the shipped extracted overlay directory in signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/.",
    )
    ap.add_argument(
        "--allow-external-rar",
        action="store_true",
        help="Allow external RAR extractors from trusted system paths (disabled by default)",
    )
    ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args()

    run_id = _run_id(a.seed)
    run_dir = allocate_run_dir(run_id)
    tmp_dir = run_dir / "overlay_extract_tmp"

    src = Path(a.overlay) if a.overlay else SHIPPED_DEFAULT
    if a.from_src:
        src = SHIPPED_DEFAULT.resolve()
    if not src.is_absolute():
        src = _REPO_ROOT / src
    src_present = src.exists()
    kind = "dir" if src.is_dir() else ("zip" if src.suffix.lower() == ".zip" else ("rar" if src.suffix.lower() == ".rar" else "unknown"))

    overall, notes = "PASS", []
    extractor, extract_rc, extract_tail = "none", None, ""
    copied = skipped = 0
    source_file_count = 0

    if not src_present:
        overall = "INCOMPLETE"
        notes.append(f"missing overlay source: {_rel(src)}")
    elif kind == "dir":
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        source_file_count = _count_regular_files(src)
        copied, skipped = _copy_no_overwrite(src, OUT_ROOT)
        extractor = "dircopy"
        notes.append(f"copied={copied} skipped_existing={skipped}")
        if source_file_count == 0:
            overall = "FAIL"
            notes.append("overlay source is empty; refusing no-op apply")
    elif kind == "zip":
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            _safe_extract_zip(src, tmp_dir)
            source_file_count = _count_regular_files(tmp_dir)
            copied, skipped = _copy_no_overwrite(tmp_dir, OUT_ROOT)
            extractor = "zipfile"
            notes.append(f"copied={copied} skipped_existing={skipped}")
            if source_file_count == 0:
                overall = "FAIL"
                notes.append("overlay archive contains no regular files; refusing no-op apply")
        except Exception as e:
            overall = "FAIL"
            notes.append(f"zip extract failed: {type(e).__name__}: {e}")
    elif kind == "rar":
        if not a.allow_external_rar:
            overall = "INCOMPLETE"
            notes.append("RAR extraction disabled by default; use --allow-external-rar or provide --overlay .zip")
        else:
            picked = _pick_extractor()
            if picked is None:
                extractor = "none"
                overall = "INCOMPLETE"
                notes.append("no trusted rar extractor found in system paths")
            else:
                extractor, extractor_exe = picked
                OUT_ROOT.mkdir(parents=True, exist_ok=True)
                extract_rc, extract_tail = _extract_rar(extractor, extractor_exe, src, tmp_dir, run_dir=run_dir)
                if extract_rc != 0:
                    overall = "FAIL"
                    notes.append(f"extractor failed: {extractor} rc={extract_rc}")
                else:
                    try:
                        _validate_extracted_tree(tmp_dir)
                        source_file_count = _count_regular_files(tmp_dir)
                        copied, skipped = _copy_no_overwrite(tmp_dir, OUT_ROOT)
                        notes.append(f"copied={copied} skipped_existing={skipped}")
                        if source_file_count == 0:
                            overall = "FAIL"
                            notes.append("overlay archive contains no regular files; refusing no-op apply")
                    except Exception as e:
                        overall = "FAIL"
                        notes.append(f"unsafe rar extraction output: {type(e).__name__}: {e}")
    else:
        overall = "INCOMPLETE"
        notes.append("unsupported overlay source (use .zip, .rar, or directory)")

    if (kind in ("zip", "rar")) and (not a.keep_tmp) and tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    report = {
        "schema_version": "signal_fidelity_apply_report@1",
        "run_id": run_id,
        "issue_id": a.issue,
        "seed": a.seed,
        "overall": overall,
        "archive_present": bool(src_present),
        "extractor": extractor,
        "archive_rel": _rel(src) if src_present else None,
        "source_kind": kind,
        "out_root_rel": _rel(OUT_ROOT),
        "source_file_count": source_file_count,
        "copied_files": copied,
        "skipped_existing": skipped,
        "extractor_rc": extract_rc,
        "extractor_output_tail": extract_tail,
        "notes": notes,
        "deterministic": True,
    }
    write_json((run_dir / "signal_fidelity_apply_report.json"), report)
    (run_dir / "signal_fidelity_apply_summary.md").write_text(
        "\n".join(
            [
                f"# Signal Fidelity Overlay Apply - {overall}",
                "",
                f"- issue: {a.issue}",
                f"- run_id: {run_id}",
                f"- source: {kind} ({_rel(src)})",
                f"- extractor: {extractor}",
                f"- source_file_count: {source_file_count}",
                f"- copied_files: {copied}",
                f"- skipped_existing: {skipped}",
                "",
                "## Notes",
                *([f"- {n}" for n in notes] if notes else ["- (none)"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        (run_dir / "run.json"),
        {
            "run_id": run_id,
            "issue_id": a.issue,
            "seed": a.seed,
            "deterministic": True,
            "outputs": ["signal_fidelity_apply_report.json", "signal_fidelity_apply_summary.md", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )
    print(f"{overall}: wrote outputs to {run_dir}")
    return 1 if overall == "FAIL" else (2 if overall == "INCOMPLETE" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
