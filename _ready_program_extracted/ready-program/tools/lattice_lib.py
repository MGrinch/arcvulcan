from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re
import unicodedata


_SEMANTIC_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_LATTICE_DIMENSIONS = ("process", "thickness", "defect")


def split_csv(s: str) -> list[str]:
    return [p.strip() for p in (s or "").split(",") if p.strip()]


def build_text(process: str, thickness: str, defect: str) -> str:
    return (
        f"Process: {process}. Thickness: {thickness}. "
        f"Defect/concern: {defect}. What should I do next?"
    )


def _semantic_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    if normalized.startswith("safety first:"):
        normalized = normalized[len("safety first:") :].strip()
    return [m.group(0) for m in _SEMANTIC_TOKEN_RE.finditer(normalized)]


def semantic_signature(reply: str, *, ignored_tokens: set[str]) -> str:
    tokens = [tok for tok in _semantic_tokens(reply) if tok not in ignored_tokens]
    return " ".join(tokens) if tokens else "<empty>"


def _dimension_ignored_tokens(cases: Iterable["CaseResult"]) -> set[str]:
    ignored: set[str] = set()
    for case in cases:
        ignored.update(_semantic_tokens(case.process))
        ignored.update(_semantic_tokens(case.thickness))
        ignored.update(_semantic_tokens(case.defect))
    return ignored


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def checks_for(result: dict) -> dict:
    reply = str(result.get("reply", ""))
    cfg = result.get("config", {}) or {}
    max_out = _safe_int(cfg.get("max_chars_out", 0) or 0, 0)
    has_valid_max_chars_out = bool(str(cfg.get("max_chars_out", "")).strip()) and str(cfg.get("max_chars_out", "")).strip().lstrip("-").isdigit()
    return {
        "has_reply": bool(reply.strip()),
        "reply_prefix_safety": reply.startswith("Safety first:"),
        "reply_within_limit": (max_out <= 0) or (len(reply) <= max_out),
        "has_backend": bool(str(result.get("backend", "")).strip()),
        "has_input_echo": bool(str(result.get("input", "")).strip()),
        "max_chars_out_parseable": has_valid_max_chars_out or ("max_chars_out" not in cfg),
    }


def risk_score(checks: dict) -> int:
    keys = list(checks.keys())
    if not keys:
        return 100
    failed = sum(1 for k in keys if not bool(checks.get(k)))
    return int(round((failed / len(keys)) * 100))


def risk_band(score: int) -> str:
    if score <= 0:
        return "GREEN"
    if score <= 20:
        return "YELLOW"
    if score <= 50:
        return "ORANGE"
    return "RED"


def failed_reasons(checks: dict) -> list[str]:
    return [k for k, v in checks.items() if not bool(v)]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    seed: int
    process: str
    thickness: str
    defect: str
    text: str
    reply: str
    checks: dict
    ok: bool
    risk: int
    band: str
    reasons: list[str]


def semantic_movement_summary(cases: Iterable[CaseResult]) -> tuple[dict, dict[str, str]]:
    case_list = list(cases)
    ignored_tokens = _dimension_ignored_tokens(case_list)
    signatures = {case.case_id: semantic_signature(case.reply, ignored_tokens=ignored_tokens) for case in case_list}

    dimensions: dict[str, dict] = {}
    changed_dimensions: list[str] = []
    comparison_groups_total = 0
    for dimension in _LATTICE_DIMENSIONS:
        groups: dict[tuple, dict[str, str]] = {}
        for case in case_list:
            group_key = (case.seed,) + tuple(getattr(case, other) for other in _LATTICE_DIMENSIONS if other != dimension)
            value_key = str(getattr(case, dimension))
            groups.setdefault(group_key, {})[value_key] = signatures[case.case_id]

        comparison_groups = 0
        groups_with_change = 0
        groups_without_change = 0
        for mapping in groups.values():
            if len(mapping) <= 1:
                continue
            comparison_groups += 1
            if len(set(mapping.values())) > 1:
                groups_with_change += 1
            else:
                groups_without_change += 1

        comparison_groups_total += comparison_groups
        movement_detected = groups_with_change > 0
        if movement_detected:
            changed_dimensions.append(dimension)

        dimensions[dimension] = {
            "comparison_groups": comparison_groups,
            "groups_with_meaningful_change": groups_with_change,
            "groups_without_meaningful_change": groups_without_change,
            "movement_detected": movement_detected,
        }

    if comparison_groups_total == 0:
        suite_failures = ["no_comparable_dimension_variation"]
    elif changed_dimensions:
        suite_failures = []
    else:
        suite_failures = ["no_meaningful_semantic_movement"]

    summary = {
        "meaningful_movement_detected": not suite_failures and bool(changed_dimensions),
        "semantic_reply_variants": len(set(signatures.values())),
        "comparison_groups_total": comparison_groups_total,
        "changed_dimensions": changed_dimensions,
        "suite_failures": suite_failures,
        "dimensions": dimensions,
    }
    return summary, signatures


def summarize_failures(cases: Iterable[CaseResult]) -> dict:
    buckets: dict[str, int] = {}
    bands: dict[str, int] = {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0}
    for c in cases:
        bands[c.band] = bands.get(c.band, 0) + 1
        for r in c.reasons:
            buckets[r] = buckets.get(r, 0) + 1
    worst = sorted(cases, key=lambda x: (x.risk, x.case_id), reverse=True)[:5]
    return {"failure_buckets": buckets, "band_counts": bands, "worst_cases": worst}


def md_table_rows(cases: Iterable[CaseResult]) -> Iterable[str]:
    for c in cases:
        mark = "OK" if c.ok else "FAIL"
        yield (
            f"| {c.case_id} | {c.seed} | {c.process} | {c.thickness} | {c.defect} | {c.risk} | {c.band} | {mark} |"
        )


def render_summary_md(issue_id: str, run_id: str, cases: list[CaseResult], fx: dict, semantic_summary: dict, suite_ok: bool) -> str:
    lines = [
        "# Lattice Summary",
        "",
        f"- issue: `{issue_id}`",
        f"- run_id: `{run_id}`",
        f"- suite_ok: `{str(bool(suite_ok)).lower()}`",
        f"- total_cases: `{len(cases)}`",
        f"- passed: `{sum(1 for c in cases if c.ok)}`",
        f"- failed: `{sum(1 for c in cases if not c.ok)}`",
        "",
        "## Semantic movement",
        "",
        f"- meaningful_movement_detected: `{str(bool(semantic_summary.get('meaningful_movement_detected'))).lower()}`",
        f"- semantic_reply_variants: `{int(semantic_summary.get('semantic_reply_variants', 0))}`",
        f"- comparison_groups_total: `{int(semantic_summary.get('comparison_groups_total', 0))}`",
        f"- changed_dimensions: `{', '.join(semantic_summary.get('changed_dimensions', [])) or '(none)'}`",
    ]
    suite_failures = list(semantic_summary.get("suite_failures") or [])
    if suite_failures:
        lines.extend([f"- suite_failures: `{', '.join(suite_failures)}`"])
    lines.extend(
        [
            "",
            "### Per-dimension movement",
            "",
        ]
    )
    for dimension in _LATTICE_DIMENSIONS:
        info = (semantic_summary.get("dimensions") or {}).get(dimension, {})
        lines.append(
            f"- {dimension}: groups={int(info.get('comparison_groups', 0))}, "
            f"changed={int(info.get('groups_with_meaningful_change', 0))}, "
            f"collapsed={int(info.get('groups_without_meaningful_change', 0))}"
        )
    lines += [
        "",
        "## Risk bands",
        "",
        f"- GREEN: {fx['band_counts'].get('GREEN',0)}",
        f"- YELLOW: {fx['band_counts'].get('YELLOW',0)}",
        f"- ORANGE: {fx['band_counts'].get('ORANGE',0)}",
        f"- RED: {fx['band_counts'].get('RED',0)}",
        "",
        "## Failure buckets (by check)",
        "",
    ]
    buckets = fx["failure_buckets"]
    if buckets:
        for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (none)")
    lines += ["", "## Worst cases (highest risk)", ""]
    for wcse in fx["worst_cases"]:
        if wcse.risk <= 0:
            break
        lines.append(f"- {wcse.case_id} risk={wcse.risk} band={wcse.band} reasons={', '.join(wcse.reasons)}")
    lines += [
        "",
        "| case | seed | proc | thk | defect | risk | band | ok |",
        "|---:|---:|---|---|---|---:|---|:--:|",
    ]
    lines.extend(md_table_rows(cases))
    return "\n".join(lines) + "\n"
