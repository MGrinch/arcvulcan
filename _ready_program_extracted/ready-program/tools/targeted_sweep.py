#!/usr/bin/env python3
"""Targeted tool sweep (offline).

Runs each tool once with lightweight arguments, producing a single report.

Exit codes:
  0 PASS (all steps 0)
  1 FAIL (any step 1)
  2 INCOMPLETE (no FAIL but some step 2)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from json_canon import write_json
from run_paths import allocate_run_dir, make_run_id

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUNPATH_RE = re.compile(r"wrote outputs to (?P<path>.+)$")
_ISSUE_RE = re.compile(r"^ISSUE-[0-9]{8}-[0-9]{3}$")
_MAX_CMD_ARG_CHARS = 4096
_MAX_STEP_TIMEOUT_S = 900
_STDOUT_EXCERPT_HEAD_CHARS = 4000
_STDOUT_EXCERPT_TAIL_CHARS = 4000
_STDOUT_INLINE_FAILURE_CHARS = 64000
_CHILD_SUMMARY_EXCERPT_CHARS = 24000
_CHILD_REPORT_EXCERPT_CHARS = 12000
_SAFE_ARG_RE = re.compile(r"^[^\x00\r\n]*$")
_ABS_PATH_RE = re.compile(r"(?i)(?:[A-Z]:\\|/)[^\s]+")


def _run_id(*, issue: str, seed: int, atheris_seconds: int) -> str:
    return make_run_id(
        "targeted_sweep",
        {
            "issue": issue,
            "seed": int(seed),
            "atheris_seconds": int(atheris_seconds),
        },
    )



def _tail(s: str, *, head: int = _STDOUT_EXCERPT_HEAD_CHARS, tail: int = _STDOUT_EXCERPT_TAIL_CHARS) -> str:
    s = s or ""
    head = max(0, int(head))
    tail = max(0, int(tail))
    if len(s) <= head + tail or (head == 0 and tail == 0):
        return s
    prefix = s[:head]
    suffix = s[-tail:] if tail else ""
    omitted = len(s) - len(prefix) - len(suffix)
    marker = f"\n… [{omitted} chars omitted] …\n"
    return prefix + marker + suffix



def _is_safe_cmd(cmd: list[str]) -> bool:
    if not cmd:
        return False
    for part in cmd:
        p = str(part or "")
        if not p or len(p) > _MAX_CMD_ARG_CHARS or not _SAFE_ARG_RE.fullmatch(p):
            return False
    return True



def _sanitize_tail_text(text: str) -> str:
    return _ABS_PATH_RE.sub("<path>", text or "")



def _step(name: str, cmd: list[str], env: dict[str, str], *, timeout_s: int, run_dir: Path) -> tuple[int, str, str, str | None]:
    if not _is_safe_cmd(cmd):
        msg = _sanitize_tail_text("unsafe subprocess arguments rejected")
        return 1, msg, msg, None
    timeout_s = max(1, min(int(timeout_s), _MAX_STEP_TIMEOUT_S))
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:64] or "step"
    logs_dir = run_dir / "step_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{slug}_{os.getpid()}_{secrets.token_hex(4)}.stdout.log"
    try:
        with log_file.open("xb") as logf:
            p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, env=env, text=True)
            try:
                rc = int(p.wait(timeout=timeout_s))
            except subprocess.TimeoutExpired as e:
                p.kill()
                p.wait(timeout=5)
                out = log_file.read_text(encoding="utf-8", errors="replace")
                raw_out = f"timeout after {timeout_s}s: {e}\n{out}"
                safe_out = _sanitize_tail_text(raw_out)
                log_file.write_text(safe_out, encoding="utf-8")
                return 1, raw_out, safe_out, _rel_to(run_dir, str(log_file))
        out = log_file.read_text(encoding="utf-8", errors="replace")
        safe_out = _sanitize_tail_text(out)
        log_file.write_text(safe_out, encoding="utf-8")
        return rc, out, safe_out, _rel_to(run_dir, str(log_file))
    except Exception as e:
        raw_out = f"execution error: {type(e).__name__}: {e}"
        safe_out = _sanitize_tail_text(raw_out)
        return 1, raw_out, safe_out, None



def _extract_path(out_text: str, expected_root: Path) -> str | None:
    lines = (out_text or "").strip().splitlines()
    if not lines:
        return None
    m = _RUNPATH_RE.search(lines[-1].strip())
    if not m:
        return None
    p = Path(m.group("path"))
    try:
        p_resolved = p.resolve()
        p_resolved.relative_to(expected_root.resolve())
    except Exception:
        return None
    return str(p_resolved)



def _rel_to(base: Path, raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    p = Path(raw_path)
    try:
        return str(p.resolve().relative_to(base.resolve())).replace("\\", "/")
    except Exception:
        return p.name



def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


_ALLOW_EXTERNAL_CHILD_TOOLS = {
    "tools/repro_replay_diff.py",
    "tools/protocol_drift_radar.py",
    "tools/mirror_calibration_bench.py",
}


@lru_cache(maxsize=None)
def _tool_supports_allow_external_path(tool_rel: str) -> bool:
    if not tool_rel:
        return False
    normalized = Path(tool_rel).as_posix()
    if normalized in _ALLOW_EXTERNAL_CHILD_TOOLS:
        return True
    source_path = (_REPO_ROOT / normalized).resolve()
    try:
        source_path.relative_to(_REPO_ROOT.resolve())
    except Exception:
        return False
    if not source_path.is_file():
        return False
    try:
        source = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return bool(re.search(r"add_argument\([^\n]*[\"']--allow-external-path[\"']", source))


_SEED_AWARE_CHILD_TOOLS = {
    "tools/apply_signal_fidelity_overlay.py",
    "tools/artifact_roundtrip.py",
    "tools/atheris_fuzz_router.py",
    "tools/backend_contract_probe.py",
    "tools/backend_fault_injector.py",
    "tools/coverage_gate.py",
    "tools/curriculum_corpus_linter.py",
    "tools/harness_lattice.py",
    "tools/harness_session.py",
    "tools/harness_turn.py",
    "tools/latency_cost_budget_enforcer.py",
    "tools/mirror_calibration_bench.py",
    "tools/mirror_leakage_detector.py",
    "tools/node_evolution_diff.py",
    "tools/ontario_claims_citation_guard.py",
    "tools/prompt_snapshot_guard.py",
    "tools/property_turn_fuzzer.py",
    "tools/protocol_drift_radar.py",
    "tools/redteam_injection_suite.py",
    "tools/redteam_rag_poisoning_suite.py",
    "tools/retrieval_eval_bench.py",
    "tools/seed_sweep.py",
    "tools/stage_timing_profiler.py",
}



def _with_seed(cmd: list[str], seed: int) -> list[str]:
    if "--seed" in cmd:
        return list(cmd)
    if len(cmd) < 2:
        return list(cmd)
    tool_rel = Path(cmd[1]).as_posix()
    if tool_rel not in _SEED_AWARE_CHILD_TOOLS:
        return list(cmd)
    return [*cmd, "--seed", str(int(seed))]



def _with_allow_external_path(cmd: list[str], *paths: str | None) -> list[str]:
    if "--allow-external-path" in cmd:
        return list(cmd)
    if len(cmd) < 2:
        return list(cmd)
    tool_rel = Path(cmd[1]).as_posix()
    if not _tool_supports_allow_external_path(tool_rel):
        return list(cmd)
    for raw in paths:
        if not raw:
            continue
        if not _is_within(_REPO_ROOT, Path(raw)):
            return [*cmd, "--allow-external-path"]
    return list(cmd)



def _allocate_sweep_run_dir(run_id: str) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="daedalus_targeted_sweep_")).resolve()
    previous = os.environ.get("DAEDALUS_RUNS_DIR")
    try:
        os.environ["DAEDALUS_RUNS_DIR"] = str(temp_root)
        return allocate_run_dir(run_id)
    finally:
        if previous is None:
            os.environ.pop("DAEDALUS_RUNS_DIR", None)
        else:
            os.environ["DAEDALUS_RUNS_DIR"] = previous



def _coerce_seed(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return value.strip()
    return value



def _seed_from_cmd(cmd: list[str]) -> int | None:
    if "--seed" not in cmd:
        return None
    idx = cmd.index("--seed")
    if idx + 1 >= len(cmd):
        return None
    try:
        return int(str(cmd[idx + 1]).strip())
    except Exception:
        return None



def _collect_child_run_contract(child_runs: Path) -> dict[str, object]:
    run_jsons = sorted(child_runs.glob("*/run.json"))
    if not run_jsons:
        return {
            "found": 0,
            "all_deterministic": False,
            "all_artifact_content_stable": False,
            "child_runs": [],
        }

    child_rows: list[dict[str, object]] = []
    for run_json in run_jsons:
        try:
            meta = json.loads(run_json.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            meta = {}
        deterministic = bool(meta.get("deterministic"))
        artifact_identity_stable = bool(meta.get("artifact_identity_stable", False))
        artifact_content_stable = bool(meta.get("artifact_content_stable", deterministic and artifact_identity_stable))
        child_rows.append(
            {
                "run_dir": run_json.parent.name,
                "run_id": meta.get("run_id", run_json.parent.name),
                "deterministic": deterministic,
                "artifact_identity_stable": artifact_identity_stable,
                "artifact_content_stable": artifact_content_stable,
            }
        )

    return {
        "found": len(child_rows),
        "all_deterministic": all(bool(row.get("deterministic")) for row in child_rows),
        "all_artifact_identity_stable": all(bool(row.get("artifact_identity_stable")) for row in child_rows),
        "all_artifact_content_stable": all(
            bool(row.get("artifact_identity_stable")) and bool(row.get("artifact_content_stable"))
            for row in child_rows
        ),
        "child_runs": child_rows,
    }



def _validate_child_run_seeds(child_runs: Path, expected_by_run_dir: dict[str, int]) -> tuple[int, str]:
    if not expected_by_run_dir:
        return 2, "INCOMPLETE: no seeded child runs were available for validation"

    checked = 0
    mismatches: list[str] = []
    unreadable: list[str] = []
    missing: list[str] = []
    tracked_dirs = {str(Path(raw).resolve()) for raw in expected_by_run_dir}

    for raw_dir, expected_seed in sorted(expected_by_run_dir.items()):
        run_dir = Path(raw_dir).resolve()
        run_file = run_dir / "run.json"
        rel = _rel_to(child_runs, str(run_file)) or run_file.name
        if not run_file.exists():
            missing.append(rel)
            continue
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except Exception as e:
            unreadable.append(f"{rel} ({type(e).__name__}: {e})")
            continue
        if not isinstance(data, dict):
            unreadable.append(f"{rel} (expected object, got {type(data).__name__})")
            continue
        if "seed" not in data:
            unreadable.append(f"{rel} (missing seed field)")
            continue
        checked += 1
        actual = _coerce_seed(data.get("seed"))
        expected = _coerce_seed(expected_seed)
        if actual != expected:
            mismatches.append(f"{rel} expected {expected!r} got {actual!r}")

    extras: list[str] = []
    for run_file in sorted(child_runs.rglob("run.json")):
        parent = str(run_file.parent.resolve())
        if parent in tracked_dirs:
            continue
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and "seed" in data:
            rel = _rel_to(child_runs, str(run_file)) or run_file.name
            extras.append(rel)

    if missing or unreadable or mismatches or extras:
        parts: list[str] = []
        if mismatches:
            parts.append("mismatched seeds: " + "; ".join(mismatches))
        if missing:
            parts.append("missing run.json: " + "; ".join(missing))
        if unreadable:
            parts.append("invalid run.json: " + "; ".join(unreadable))
        if extras:
            parts.append("untracked seeded run.json: " + "; ".join(extras))
        return 1, "FAIL: " + " | ".join(parts)
    return 0, f"PASS: validated {checked} seeded child run.json file(s)"



def _report_stdout_text(text: str, *, exit_code: int) -> str:
    text = text or ""
    if exit_code == 0:
        return _tail(text)
    head = _STDOUT_INLINE_FAILURE_CHARS // 2
    tail = _STDOUT_INLINE_FAILURE_CHARS - head
    return _tail(text, head=head, tail=tail)



def _child_output_paths(child_run_dir: Path, outputs: list[str]) -> list[str]:
    rels: list[str] = []
    for raw in outputs:
        value = str(raw or "").strip()
        if not value:
            continue
        if value.endswith("/"):
            rels.append((child_run_dir / value[:-1]).as_posix())
        else:
            rels.append((child_run_dir / value).as_posix())
    return rels



def _read_child_run_meta(child_run_dir: Path) -> dict[str, object]:
    run_json = child_run_dir / "run.json"
    if not run_json.exists():
        return {}
    try:
        data = json.loads(run_json.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _format_report_scalar(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).strip()
    return text or None


def _extend_report_lines(lines: list[str], title: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, list):
        items = [item for item in value if item not in (None, "", [], {})]
        if not items:
            return
        lines.append(f"{title}:")
        for item in items[:20]:
            if isinstance(item, dict):
                rendered = json.dumps(item, ensure_ascii=False, sort_keys=True)
            else:
                rendered = _format_report_scalar(item)
            if rendered:
                lines.append(f"- {rendered}")
        return
    if isinstance(value, dict):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if rendered:
            lines.append(f"{title}: {rendered}")
        return
    rendered = _format_report_scalar(value)
    if rendered:
        lines.append(f"{title}: {rendered}")


def _report_excerpt_text(report_path: Path) -> str:
    try:
        raw = report_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"unreadable report: {type(e).__name__}: {e}"
    try:
        payload = json.loads(raw)
    except Exception:
        return _tail(_sanitize_tail_text(raw), head=_CHILD_REPORT_EXCERPT_CHARS // 2, tail=_CHILD_REPORT_EXCERPT_CHARS - (_CHILD_REPORT_EXCERPT_CHARS // 2))

    lines: list[str] = []
    if isinstance(payload, dict):
        preferred_keys = (
            "overall",
            "status",
            "summary",
            "message",
            "problems",
            "warnings",
            "errors",
            "findings",
            "details",
            "gaps",
            "failures",
        )
        for key in preferred_keys:
            if key in payload:
                _extend_report_lines(lines, key, payload.get(key))
    if not lines:
        if isinstance(payload, (dict, list)):
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            scalar = _format_report_scalar(payload)
            if scalar:
                lines.append(scalar)
    excerpt = _sanitize_tail_text("\n".join(lines))
    return _tail(
        excerpt,
        head=_CHILD_REPORT_EXCERPT_CHARS // 2,
        tail=_CHILD_REPORT_EXCERPT_CHARS - (_CHILD_REPORT_EXCERPT_CHARS // 2),
    )



def _resolve_child_output(child_run_dir: Path, rel_path: str) -> Path | None:
    target = (child_run_dir / rel_path).resolve()
    if not _is_within(child_run_dir, target):
        return None
    if not target.exists() or not target.is_file():
        return None
    return target



def _load_child_artifact_context(child_run_dir: Path, *, run_dir: Path) -> dict[str, object]:
    child_run_dir = child_run_dir.resolve()
    context: dict[str, object] = {
        "child_run_dir": _rel_to(run_dir, str(child_run_dir)) or child_run_dir.name,
    }
    meta = _read_child_run_meta(child_run_dir)
    outputs_raw = meta.get("outputs") if isinstance(meta.get("outputs"), list) else []
    outputs = [str(item) for item in outputs_raw if isinstance(item, str)]
    if outputs:
        context["child_outputs"] = _child_output_paths(child_run_dir, outputs)

    summary_candidates: list[Path] = []
    for rel_path in outputs:
        if rel_path.endswith("_summary.md"):
            target = _resolve_child_output(child_run_dir, rel_path)
            if target is not None:
                summary_candidates.append(target)
    if not summary_candidates:
        summary_candidates.extend(sorted(child_run_dir.glob("*_summary.md")))

    report_candidates: list[Path] = []
    for rel_path in outputs:
        if rel_path.endswith("_report.json"):
            target = _resolve_child_output(child_run_dir, rel_path)
            if target is not None:
                report_candidates.append(target)
    if not report_candidates:
        report_candidates.extend(sorted(child_run_dir.glob("*_report.json")))

    report_path: Path | None = None
    if report_candidates:
        report_path = report_candidates[0]
        context["child_report"] = _rel_to(run_dir, str(report_path)) or report_path.name

    if summary_candidates:
        summary_path = summary_candidates[0]
        summary_text = _sanitize_tail_text(summary_path.read_text(encoding="utf-8", errors="replace"))
        context["child_summary"] = _rel_to(run_dir, str(summary_path)) or summary_path.name
        context["child_summary_excerpt"] = _tail(
            summary_text,
            head=_CHILD_SUMMARY_EXCERPT_CHARS // 2,
            tail=_CHILD_SUMMARY_EXCERPT_CHARS - (_CHILD_SUMMARY_EXCERPT_CHARS // 2),
        )
    elif report_path is not None:
        context["child_report_excerpt"] = _report_excerpt_text(report_path)

    return context



def _augment_step_stdout(stdout_text: str, *, exit_code: int, child_context: dict[str, object] | None) -> str:
    rendered = _report_stdout_text(stdout_text, exit_code=exit_code)
    if exit_code == 0 or not child_context:
        return rendered
    summary_excerpt = str(child_context.get("child_summary_excerpt") or "").strip()
    if summary_excerpt:
        summary_rel = str(child_context.get("child_summary") or "summary.md").strip() or "summary.md"
        if summary_excerpt in rendered:
            return rendered
        banner = f"--- child summary: {summary_rel} ---"
        if rendered.strip():
            return rendered.rstrip() + "\n\n" + banner + "\n" + summary_excerpt
        return banner + "\n" + summary_excerpt

    report_excerpt = str(child_context.get("child_report_excerpt") or "").strip()
    if not report_excerpt:
        return rendered
    report_rel = str(child_context.get("child_report") or "report.json").strip() or "report.json"
    if report_excerpt in rendered:
        return rendered
    banner = f"--- child report: {report_rel} ---"
    if rendered.strip():
        return rendered.rstrip() + "\n\n" + banner + "\n" + report_excerpt
    return banner + "\n" + report_excerpt



def _record_step(
    *,
    name: str,
    prepared_cmd: list[str],
    step_result: tuple[int, str, str, str | None],
    child_runs: Path,
    run_dir: Path,
) -> tuple[dict[str, object], str | None, int | None]:
    rc, raw_out, safe_out, log_path = step_result
    child_run_dir = _extract_path(raw_out, expected_root=child_runs)
    child_context = _load_child_artifact_context(Path(child_run_dir), run_dir=run_dir) if child_run_dir else None
    step = {
        "name": name,
        "exit_code": rc,
        "stdout_tail": _augment_step_stdout(safe_out, exit_code=rc, child_context=child_context),
    }
    if log_path:
        step["stdout_log"] = log_path
    if child_context:
        step.update(child_context)
    expected_seed = _seed_from_cmd(prepared_cmd)
    return step, child_run_dir, expected_seed



def main() -> int:
    ap = argparse.ArgumentParser(prog="targeted_sweep")
    ap.add_argument("--issue", required=True, help="ISSUE-YYYYMMDD-NNN")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--atheris-seconds", type=int, default=1)
    ap.add_argument("--step-timeout", type=int, default=120, help="max seconds per subprocess step")
    a = ap.parse_args()

    if not _ISSUE_RE.match(a.issue):
        print("FAIL: issue must match ISSUE-YYYYMMDD-NNN (NNN=3 digits)")
        return 1

    env = dict(os.environ)
    py = sys.executable

    run_id = _run_id(issue=a.issue, seed=a.seed, atheris_seconds=a.atheris_seconds)
    run_dir = _allocate_sweep_run_dir(run_id)
    child_runs = (run_dir / "child_runs").resolve()
    child_runs.mkdir(parents=True, exist_ok=True)
    env["DAEDALUS_RUNS_DIR"] = str(child_runs)

    steps: list[dict] = []
    overall = "PASS"
    expected_child_seeds: dict[str, int] = {}

    def add(name: str, cmd: list[str], *allow_external_paths: str | None) -> tuple[int, str | None]:
        nonlocal overall
        prepared_cmd = _with_seed(_with_allow_external_path(cmd, *allow_external_paths), a.seed)
        step, child_run_dir, expected_seed = _record_step(
            name=name,
            prepared_cmd=prepared_cmd,
            step_result=_step(name, prepared_cmd, env, timeout_s=max(1, int(a.step_timeout)), run_dir=run_dir),
            child_runs=child_runs,
            run_dir=run_dir,
        )
        steps.append(step)
        rc = int(step["exit_code"])
        if child_run_dir and expected_seed is not None:
            expected_child_seeds[str(Path(child_run_dir).resolve())] = int(expected_seed)
        if rc == 1:
            overall = "FAIL"
        elif rc == 2 and overall != "FAIL":
            overall = "INCOMPLETE"
        return rc, child_run_dir

    # Primary harness artifacts
    rc_sess, sess_dir = add(
        "harness_session_mirror",
        [py, "tools/harness_session.py", "--issue", a.issue, "--seed", str(a.seed), "--max-turns", str(a.max_turns), "--enable-mirror", "--grounding"],
    )
    rc_sess2, sess2_dir = add(
        "harness_session_diff",
        [py, "tools/harness_session.py", "--issue", a.issue, "--seed", str(a.seed + 1), "--max-turns", str(a.max_turns)],
    )

    # Dummy overlay (zip) for the overlay tool
    overlay_zip = run_dir / "dummy_overlay.zip"
    with zipfile.ZipFile(overlay_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", "dummy overlay for tool sweep\n")

    # Repo-level checks
    add("doctor", [py, "tools/doctor.py"])
    add("selfcheck", [py, "tools/selfcheck.py"])
    add("secret_scanner", [py, "tools/secret_scanner.py", "--issue", a.issue])
    add("prompt_snapshot_guard", [py, "tools/prompt_snapshot_guard.py", "--issue", a.issue])
    add("doc_code_link_checker", [py, "tools/doc_code_link_checker.py", "--issue", a.issue, "--enforce"])
    add("curriculum_corpus_linter", [py, "tools/curriculum_corpus_linter.py", "--issue", a.issue])
    add("coverage_gate", [py, "tools/coverage_gate.py", "--issue", a.issue])
    add("latency_cost_budget_enforcer", [py, "tools/latency_cost_budget_enforcer.py", "--issue", a.issue])
    add("stage_timing_profiler", [py, "tools/stage_timing_profiler.py", "--issue", a.issue])

    # Harnesses
    add("harness_turn", [py, "tools/harness_turn.py", "--issue", a.issue, "--seed", str(a.seed), "--text", "tack spacing on uneven fit-up?"])
    add("harness_lattice", [py, "tools/harness_lattice.py", "--issue", a.issue, "--seed", str(a.seed)])
    add("backend_contract_probe", [py, "tools/backend_contract_probe.py", "--issue", a.issue, "--seed", str(a.seed)])
    add("backend_fault_injector", [py, "tools/backend_fault_injector.py", "--issue", a.issue, "--seed", str(a.seed)])
    add("retrieval_eval_bench", [py, "tools/retrieval_eval_bench.py", "--issue", a.issue, "--seed", str(a.seed), "--k", "3"])
    add("seed_sweep", [py, "tools/seed_sweep.py", "--issue", a.issue, "--seed-start", "1", "--seed-end", "5", "--max-unique-replies", "50"])
    add("property_turn_fuzzer", [py, "tools/property_turn_fuzzer.py", "--issue", a.issue, "--cases", "20", "--max-len", "80"])
    add("atheris_fuzz_router", [py, "tools/atheris_fuzz_router.py", "--issue", a.issue, "--seconds", str(a.atheris_seconds)])
    add("redteam_injection_suite", [py, "tools/redteam_injection_suite.py", "--issue", a.issue, "--seed", str(a.seed)])
    add("redteam_rag_poisoning_suite", [py, "tools/redteam_rag_poisoning_suite.py", "--issue", a.issue, "--seed", str(a.seed)])
    add("mutation_suite", [py, "tools/mutation_suite.py", "--issue", a.issue, "--engine", "builtin", "--target", "xyzgl", "--dry-run"])
    add("apply_signal_fidelity_overlay", [py, "tools/apply_signal_fidelity_overlay.py", "--issue", a.issue, "--overlay", str(overlay_zip)])

    # Run-dir based checks (only if we located a harness dir)
    if sess_dir and Path(sess_dir).exists():
        add("validate_schemas", [py, "tools/validate_schemas.py", sess_dir])
        add("artifact_roundtrip", [py, "tools/artifact_roundtrip.py", "--issue", a.issue, sess_dir])
        add("graph_invariant_checker", [py, "tools/graph_invariant_checker.py", "--issue", a.issue, sess_dir])
        add("reground_cadence_verifier", [py, "tools/reground_cadence_verifier.py", "--issue", a.issue, "--every", "5", sess_dir])
        add("repro_replay_diff", [py, "tools/repro_replay_diff.py", "--issue", a.issue, sess_dir], sess_dir)
        add("protocol_drift_radar", [py, "tools/protocol_drift_radar.py", "--issue", a.issue, sess_dir], sess_dir)
        add("mirror_leakage_detector", [py, "tools/mirror_leakage_detector.py", "--issue", a.issue, sess_dir])
        add("mirror_calibration_bench", [py, "tools/mirror_calibration_bench.py", "--issue", a.issue, "--min-avg", "0.35", sess_dir], sess_dir)
        add("ontario_claims_citation_guard", [py, "tools/ontario_claims_citation_guard.py", "--issue", a.issue, sess_dir])
    else:
        steps.append({"name": "session_dir", "exit_code": 2, "stdout_tail": "INCOMPLETE: could not locate session run dir"})
        if overall != "FAIL":
            overall = "INCOMPLETE"

    # Node evolution diff needs two graphs
    if sess_dir and sess2_dir and Path(sess_dir).exists() and Path(sess2_dir).exists():
        before = str(Path(sess_dir) / "knowledge_graph.json")
        after = str(Path(sess2_dir) / "knowledge_graph.json")
        add(
            "node_evolution_diff",
            [py, "tools/node_evolution_diff.py", "--issue", a.issue, before, after, "--session-report", str(Path(sess_dir) / "session_report.json")],
        )
    else:
        steps.append({"name": "node_evolution_inputs", "exit_code": 2, "stdout_tail": "INCOMPLETE: missing before/after session dirs"})
        if overall != "FAIL":
            overall = "INCOMPLETE"

    rc_seed_check, out_seed_check = _validate_child_run_seeds(child_runs, expected_child_seeds)
    steps.append({"name": "child_seed_consistency", "exit_code": rc_seed_check, "stdout_tail": out_seed_check})
    if rc_seed_check == 1:
        overall = "FAIL"
    elif rc_seed_check == 2 and overall != "FAIL":
        overall = "INCOMPLETE"

    child_contract = _collect_child_run_contract(child_runs)
    parent_deterministic = bool(child_contract.get("found")) and bool(child_contract.get("all_deterministic"))
    parent_artifact_content_stable = bool(child_contract.get("found")) and bool(child_contract.get("all_artifact_content_stable"))
    parent_artifact_identity_stable = True

    report = {
        "schema_version": "targeted_sweep_report@1",
        "run_id": run_id,
        "issue_id": a.issue,
        "seed": a.seed,
        "overall": overall,
        "runs_root": _rel_to(run_dir, str(child_runs)),
        "artifacts": {"session_dir": _rel_to(run_dir, sess_dir), "session2_dir": _rel_to(run_dir, sess2_dir), "step_logs_dir": "step_logs"},
        "child_run_contract": child_contract,
        "steps": steps,
    }
    write_json(run_dir / "targeted_sweep_report.json", report)
    (run_dir / "targeted_sweep_summary.md").write_text(
        "\n".join(
            [
                f"# Targeted Sweep — {overall}",
                "",
                f"- issue: {a.issue}",
                f"- run_id: {run_id}",
                f"- runs_root: {_rel_to(run_dir, str(child_runs))}",
                f"- session_dir: {_rel_to(run_dir, sess_dir)}",
                f"- session2_dir: {_rel_to(run_dir, sess2_dir)}",
                "",
                "## Steps",
                *[f"- **{s['name']}**: `{s['exit_code']}`" for s in steps],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        run_dir / "run.json",
        {
            "run_id": run_id,
            "issue_id": a.issue,
            "seed": a.seed,
            "deterministic": parent_deterministic,
            "artifact_identity_stable": parent_artifact_identity_stable,
            "artifact_content_stable": parent_artifact_content_stable,
            "determinism_basis": "derived from child run.json contracts plus the fixed top-level sweep invocation; parent content stability requires child identity stability",
            "outputs": ["targeted_sweep_report.json", "targeted_sweep_summary.md", "dummy_overlay.zip", "step_logs", "run.json"],
            "exit_codes": {"0": "PASS", "1": "FAIL", "2": "INCOMPLETE"},
        },
    )

    print(f"{overall}: wrote outputs to {run_dir}")
    return 1 if overall == "FAIL" else (2 if overall == "INCOMPLETE" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
