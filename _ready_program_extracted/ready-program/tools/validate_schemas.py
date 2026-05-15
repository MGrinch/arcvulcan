#!/usr/bin/env python3
from __future__ import annotations

import argparse
import warnings
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

# Keep zip-distributed repos clean (avoid creating __pycache__/ during validation runs)
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

try:
    import jsonschema
except Exception:  # pragma: no cover
    jsonschema = None

warnings.filterwarnings('ignore', category=DeprecationWarning)

_REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = _REPO_ROOT / "schemas"
MAX_JSON_BYTES = 5_000_000
MAX_SCHEMA_ERRORS = 200
_SCHEMA_CACHE: dict[str, dict] = {}


def _no_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key: {k!r}")
        out[k] = v
    return out


def _load_json(path: Path) -> dict:
    if not path.exists() or not path.is_file():
        raise ValueError(f"invalid json path: {path}")
    try:
        if int(path.stat().st_size) > MAX_JSON_BYTES:
            raise ValueError(f"json file too large: {path} ({path.stat().st_size} bytes > {MAX_JSON_BYTES})")
    except OSError:
        pass
    last_err: Exception | None = None
    for _ in range(3):
        try:
            raw = path.read_bytes()
            try:
                txt = raw.decode("utf-8")
            except UnicodeDecodeError:
                txt = raw.decode("utf-8", errors="replace")
            return json.loads(txt, object_pairs_hook=_no_duplicate_pairs)
        except json.JSONDecodeError as e:
            last_err = e
            time.sleep(0.05)
    raise ValueError(f"invalid JSON: {path} ({last_err})")


def _safe_schema_path(name: str) -> Path:
    raw = (name or "").strip()
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"invalid schema name: {name}")
    if len(p.parts) != 1:
        raise ValueError(f"schema must be a simple filename: {name}")
    resolved = (SCHEMA_DIR / p.name).resolve()
    resolved.relative_to(SCHEMA_DIR.resolve())
    return resolved


def _load_schema(name: str) -> dict:
    cached = _SCHEMA_CACHE.get(name)
    if cached is not None:
        return cached
    p = _safe_schema_path(name)
    if not p.exists():
        raise FileNotFoundError(f"schema not found: {p}")
    loaded = _load_json(p)
    _SCHEMA_CACHE[name] = loaded
    return loaded


def _iter_refs(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                yield v
            else:
                yield from _iter_refs(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_refs(it)


def _is_remote_or_unsafe_ref(ref: str) -> bool:
    r = (ref or "").strip()
    if not r:
        return False
    low = r.lower()
    if low.startswith("//"):
        return True
    if low.startswith(("http://", "https://", "file://", "ftp://")):
        return True
    if Path(r).is_absolute():
        return True
    parts = urlsplit(r)
    if parts.scheme and parts.scheme not in {"", "#"}:
        return True
    return False


def _validate(doc: dict, schema_name: str) -> list[str]:
    if jsonschema is None:
        return ["jsonschema not installed; cannot validate"]
    schema = _load_schema(schema_name)
    for ref in _iter_refs(schema):
        if _is_remote_or_unsafe_ref(ref):
            return [f"unsafe remote/absolute $ref blocked: {ref}"]

    # Resolve local $ref within schemas/
    def resolver(uri: str) -> dict:
        if _is_remote_or_unsafe_ref(uri):
            raise ValueError(f"unsafe remote/absolute $ref blocked: {uri}")
        no_fragment = (uri or "").split("#", 1)[0]
        if not no_fragment:
            return schema
        local = no_fragment.split("/")[-1]
        local_schema = _load_schema(local)
        for ref in _iter_refs(local_schema):
            if _is_remote_or_unsafe_ref(ref):
                raise ValueError(f"unsafe remote/absolute $ref blocked: {ref}")
        return local_schema

    resolver_obj = jsonschema.RefResolver.from_schema(schema, handlers={"": lambda u: resolver(u)})
    v = jsonschema.Draft202012Validator(schema, resolver=resolver_obj)
    errs = []
    for i, e in enumerate(v.iter_errors(doc)):
        if i >= MAX_SCHEMA_ERRORS:
            errs.append(f"too many schema errors; truncated at {MAX_SCHEMA_ERRORS}")
            break
        errs.append(e.message)
    return errs


SCHEMA_FOR_FILENAME: dict[str, str] = {
    "turn_report.json": "turn_report.schema.json",
    "turn_report.witness.json": "witness_event.schema.json",
    "lattice_report.json": "lattice_report.schema.json",
    "lattice_report.witness.json": "witness_event.schema.json",
    "run.json": "run_meta.schema.json",
    "session_report.json": "session_report.schema.json",
    "session_report.witness.json": "witness_event.schema.json",
    "knowledge_graph.json": "knowledge_graph.schema.json",
    "backend_fault_report.json": "backend_fault_report.schema.json",
    "repro_backends_smoke_report.json": "repro_backends_smoke_report.schema.json",
    "retrieval_eval_report.json": "retrieval_eval_report.schema.json",
    "coverage_report.json": "coverage_report.schema.json",
    "coverage_raw.json": "coverage_raw.schema.json",
    "protocol_drift_report.json": "protocol_drift_report.schema.json",
    "seed_sweep_report.json": "seed_sweep_report.schema.json",
    "latency_budget_report.json": "latency_budget_report.schema.json",
    "lattice_crash.json": "lattice_crash.schema.json",
    "grounding_audit_report.json": "grounding_audit_report.schema.json",
    "corpus_lint_report.json": "corpus_lint_report.schema.json",
    "node_evolution_report.json": "node_evolution_report.schema.json",
    "atheris_fuzz_report.json": "atheris_fuzz_report.schema.json",
    "backend_contract_report.json": "backend_contract_report.schema.json",
    "ontario_claims_report.json": "ontario_claims_report.schema.json",
    "mirror_calibration_report.json": "mirror_calibration_report.schema.json",
    "mirror_leakage_report.json": "mirror_leakage_report.schema.json",
    "artifact_roundtrip_report.json": "artifact_roundtrip_report.schema.json",
    "ci_gate_report.json": "ci_gate_report.schema.json",
    "repro_grounding_protocol_smoke_report.json": "repro_grounding_protocol_smoke_report.schema.json",
    "signal_fidelity_apply_report.json": "signal_fidelity_apply_report.schema.json",
    "reground_cadence_report.json": "reground_cadence_report.schema.json",
    "prompt_snapshot_report.json": "prompt_snapshot_report.schema.json",
    "prompt_snapshots.json": "prompt_snapshots.schema.json",
    "replay_diff_report.json": "replay_diff_report.schema.json",
    "graph_invariant_report.json": "graph_invariant_report.schema.json",
    "property_fuzz_report.json": "property_fuzz_report.schema.json",
    "redteam_injection_report.json": "redteam_injection_report.schema.json",
    "redteam_rag_poison_report.json": "redteam_rag_poison_report.schema.json",
    "secret_scan_report.json": "secret_scan_report.schema.json",
    "doc_link_report.json": "doc_link_report.schema.json",
    "stage_timing_report.json": "stage_timing_report.schema.json",
    "mutation_report.json": "mutation_report.schema.json",
    "targeted_sweep_report.json": "targeted_sweep_report.schema.json",
}
KNOWN_JSON_FILENAMES = tuple(SCHEMA_FOR_FILENAME)


def _guess_schema_for_filename(name: str) -> str | None:
    return SCHEMA_FOR_FILENAME.get(name)


_SCHEMAS_WITHOUT_SCHEMA_VERSION = {
    "coverage_raw.schema.json",
    "lattice_crash.schema.json",
    "run_meta.schema.json",
}


def _expected_schema_version_for_filename(name: str) -> str | None:
    schema_name = _guess_schema_for_filename(name)
    if not schema_name or schema_name in _SCHEMAS_WITHOUT_SCHEMA_VERSION:
        return None
    if schema_name == "witness_event.schema.json":
        return "witness_event@1"
    if not schema_name.endswith(".schema.json"):
        return None
    return schema_name[: -len(".schema.json")] + "@1"


def _resolve_declared_output_path(run_dir: Path, output_path: str) -> Path:
    raw = str(output_path or "").strip()
    if not raw:
        raise ValueError("declared output path is empty")
    rel = Path(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"declared output path is unsafe: {output_path!r}")
    resolved = (run_dir / rel).resolve()
    resolved.relative_to(run_dir.resolve())
    return resolved


def _collect_dir_validation_targets(run_dir: Path) -> tuple[list[Path], list[str]]:
    problems: list[str] = []
    files: list[Path] = []
    seen: set[Path] = set()

    def add_file(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(path)

    run_meta_path = run_dir / "run.json"
    if not run_meta_path.exists() or not run_meta_path.is_file():
        problems.append(f"{run_meta_path}: missing required run.json")
        return files, problems
    add_file(run_meta_path)

    for fn in KNOWN_JSON_FILENAMES:
        fp = run_dir / fn
        if fp.exists() and fp.is_file():
            add_file(fp)

    try:
        run_meta = _load_json(run_meta_path)
    except Exception as e:
        problems.append(f"{run_meta_path}: {e}")
        return files, problems

    outputs = run_meta.get("outputs")
    if not isinstance(outputs, list):
        problems.append(f"{run_meta_path}: outputs must be a list")
        return files, problems

    for raw_output in outputs:
        if not isinstance(raw_output, str):
            problems.append(f"{run_meta_path}: outputs entry must be a string: {raw_output!r}")
            continue
        try:
            resolved = _resolve_declared_output_path(run_dir, raw_output)
        except Exception as e:
            problems.append(f"{run_meta_path}: {e}")
            continue
        if not resolved.exists():
            problems.append(f"{run_meta_path}: declared output missing: {raw_output}")
            continue
        if resolved.is_file() and resolved.suffix.lower() == ".json":
            add_file(resolved)
            continue
        if resolved.is_dir():
            for nested in sorted(p for p in resolved.rglob("*.json") if p.is_file()):
                add_file(nested)
    return files, problems


def main() -> int:
    p = argparse.ArgumentParser(prog="validate_schemas")
    p.add_argument("path", help="file or runs/<run_id>/ dir")
    p.add_argument("--schema", help="schema filename in schemas/ (optional)")
    args = p.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"FAIL: not found: {target}")
        return 1

    problems: list[str] = []

    files: list[Path] = []
    if target.is_dir():
        files, dir_problems = _collect_dir_validation_targets(target)
        problems.extend(dir_problems)
    else:
        files = [target]
    if not files and not problems:
        print("FAIL: no known JSON outputs found")
        return 1

    for fp in files:
        schema_name = args.schema or _guess_schema_for_filename(fp.name)
        if not schema_name:
            problems.append(f"{fp}: cannot guess schema (use --schema)")
            continue

        try:
            doc = _load_json(fp)
            expected_schema_version = _expected_schema_version_for_filename(fp.name)
            actual_schema_version = str(doc.get("schema_version") or "") if isinstance(doc, dict) else ""
            if expected_schema_version and actual_schema_version != expected_schema_version:
                problems.append(
                    f"{fp} -> {schema_name}: schema_version mismatch (expected {expected_schema_version!r}, got {actual_schema_version!r})"
                )
            errs = _validate(doc, schema_name)
            if errs:
                problems.append(f"{fp} -> {schema_name}: " + "; ".join(errs))
        except Exception as e:
            problems.append(f"{fp} -> {schema_name}: {e}")

    if problems:
        print("FAIL:")
        for pr in problems:
            print(" -", pr)
        return 1

    print("PASS: schemas validated")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
