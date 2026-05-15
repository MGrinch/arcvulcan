from __future__ import annotations

import re


REPORT_EXPECTED_BUG_COUNT = 149
PATH_HINT_RE = re.compile(
    r"\b(?:xyzgl|tools|witness|documentation|curriculum|schemas)/[A-Za-z0-9_./-]+"
)


def _worker_entry(window: int, name: str, area: str) -> dict:
    return {
        "window": window,
        "kind": "worker",
        "name": name,
        "area": area,
        "role_file": "roles/worker.md",
        "queue_file": f"queues/window-{window:02d}.json",
        "state_file": f"state/window-{window:02d}.json",
        "output_root": f"out/window-{window:02d}",
    }


def _compiler_entry(window: int, kind: str, name: str, area: str, upstreams: list[int]) -> dict:
    role_file = "roles/precompiler.md" if kind == "precompile" else "roles/final-compiler.md"
    return {
        "window": window,
        "kind": kind,
        "name": name,
        "area": area,
        "role_file": role_file,
        "state_file": f"state/window-{window:02d}.json",
        "output_root": f"out/window-{window:02d}",
        "upstreams": upstreams,
    }


WINDOWS = [
    _worker_entry(1, "Runtime Router and Sanitization", "Owns router, protocol, mirror input-output, fallback, and sanitization runtime bugs."),
    _worker_entry(2, "Grounding and Prompt Assembly", "Owns grounding corpora, prompt assembly, prompt-budget guards, and grounding-path integrity bugs."),
    _worker_entry(3, "Graph, Retrieval Bench, and Curriculum Evidence", "Owns graph persistence, retrieval evidence, retrieval benchmark parity, and curriculum-evidence bugs."),
    _worker_entry(4, "Tutor Runtime and Session Logic", "Owns tutor phases, session loop semantics, learner-state continuity, CLI resume, and policy-close behavior."),
    _worker_entry(5, "Harness Turn and Artifact Integrity", "Owns harness_turn behavior, turn artifacts, witness event identity, and turn-facing run path bugs."),
    _worker_entry(6, "Session Harness and Determinism Plumbing", "Owns harness_session, seed sweep, run path, determinism controls, and session-export auditability bugs."),
    _worker_entry(7, "Replay Diff and Bundle Integrity", "Owns replay-diff behavior, strict replay semantics, and replay-facing bundle integrity bugs."),
    _worker_entry(8, "Sweep Orchestration and Repo Safety", "Owns targeted sweep execution, cadence verification, repo cleanliness, and deterministic run-path orchestration bugs."),
    _worker_entry(9, "Schema Gates and CI Bundle Routing", "Owns canonical artifact schemas, CI gate routing, smoke-report identity, and run-bundle completeness bugs."),
    _worker_entry(10, "Artifact Roundtrip and Canonical Repair", "Owns artifact roundtrip strictness, direct-file repair, nested child-run traversal, and canonical run-bundle rewrite bugs."),
    _worker_entry(11, "Workflow Companion and Prompt Governance", "Owns prompt snapshot guards, citation guards, signal-fidelity tooling, and doc-code workflow contract bugs."),
    _worker_entry(12, "Detectors, Scanners, and Drift Radar", "Owns secret scanning, drift radar, graph invariants, mirror leakage, and detector-fidelity bugs."),
    _worker_entry(13, "Backend Probes and Fault Injection", "Owns backend contract probes, backend fault injectors, and backend-side validation bugs."),
    _worker_entry(14, "Fuzzer Core and Coverage Truthfulness", "Owns property and fuzz harnesses that must report canonical artifacts, real coverage, and replayable failing evidence."),
    _worker_entry(15, "Lattice, Benches, and Adversarial Suites", "Owns sensitivity benches, calibration harnesses, and adversarial suites that must fail closed instead of reporting false green."),
    _compiler_entry(16, "precompile", "Runtime and Core Precompiler", "Precompiles worker outputs from windows 1 through 7 into one cumulative runtime stream.", [1, 2, 3, 4, 5, 6, 7]),
    _compiler_entry(17, "precompile", "Tooling and Guardrail Precompiler", "Precompiles worker outputs from windows 8 through 15 into one cumulative tooling and guardrail stream.", [8, 9, 10, 11, 12, 13, 14, 15]),
    _compiler_entry(18, "final", "Final Compiler", "Merges windows 16 and 17 into the final cumulative integrated package stream for the current cycle.", [16, 17]),
]


WORKER_BUG_IDS = {
    1: {"BUG-146", "BUG-109", "BUG-01", "BUG-02", "BUG-05", "BUG-06", "BUG-27", "BUG-28", "BUG-54", "BUG-75", "BUG-83", "BUG-95", "BUG-103"},
    2: {"BUG-110", "BUG-03", "BUG-19", "BUG-20", "BUG-48", "BUG-58", "BUG-69", "BUG-80", "BUG-88", "BUG-92", "BUG-102"},
    3: {"BUG-148", "BUG-135", "BUG-132", "BUG-59", "BUG-21", "BUG-46", "BUG-47", "BUG-70", "BUG-93", "BUG-99"},
    4: {"BUG-141", "BUG-128", "BUG-129", "BUG-121", "BUG-04", "BUG-100", "BUG-07", "BUG-08", "BUG-09", "BUG-89"},
    5: {"BUG-10", "BUG-11", "BUG-23", "BUG-24", "BUG-37", "BUG-49", "BUG-86", "BUG-60", "BUG-62", "BUG-61"},
    6: {"BUG-140", "BUG-85", "BUG-12", "BUG-13", "BUG-32", "BUG-33", "BUG-43", "BUG-50", "BUG-52", "BUG-55", "BUG-82", "BUG-84"},
    7: {"BUG-133", "BUG-117", "BUG-111", "BUG-14", "BUG-15", "BUG-16", "BUG-65", "BUG-72", "BUG-74", "BUG-90", "BUG-104"},
    8: {"BUG-147", "BUG-142", "BUG-127", "BUG-123", "BUG-119", "BUG-31", "BUG-45", "BUG-67"},
    9: {"BUG-144", "BUG-137", "BUG-120", "BUG-116", "BUG-114", "BUG-112", "BUG-113", "BUG-76"},
    10: {"BUG-134", "BUG-78", "BUG-79", "BUG-81", "BUG-94"},
    11: {"BUG-149", "BUG-145", "BUG-126", "BUG-122", "BUG-22", "BUG-38", "BUG-41", "BUG-42", "BUG-53", "BUG-77", "BUG-105", "BUG-108"},
    12: {"BUG-143", "BUG-139", "BUG-136", "BUG-130", "BUG-118", "BUG-115", "BUG-17", "BUG-18", "BUG-26", "BUG-64", "BUG-66", "BUG-71", "BUG-73", "BUG-106", "BUG-107"},
    13: {"BUG-51", "BUG-29", "BUG-30", "BUG-39", "BUG-40", "BUG-56", "BUG-57", "BUG-91", "BUG-97"},
    14: {"BUG-124", "BUG-125", "BUG-87", "BUG-25", "BUG-34", "BUG-35", "BUG-36", "BUG-44", "BUG-63", "BUG-68"},
    15: {"BUG-131", "BUG-138", "BUG-96", "BUG-98", "BUG-101"},
}


def parse_bug_sections(text: str) -> list[dict]:
    pattern = re.compile(r"^### (BUG-(\d+)):\s*(.*)$", re.M)
    matches = list(pattern.finditer(text))
    bugs: list[dict] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        severity_match = re.search(r"^- \*\*Severity:\*\*\s*(.*)$", section, re.M)
        phase_match = re.search(r"^- \*\*Phase:\*\*\s*(.*)$", section, re.M)
        files = sorted(dict.fromkeys(PATH_HINT_RE.findall(section)))
        bugs.append(
            {
                "bug_id": match.group(1),
                "num": int(match.group(2)),
                "title": match.group(3).strip(),
                "severity": severity_match.group(1).strip() if severity_match else "",
                "phase": phase_match.group(1).strip() if phase_match else "",
                "files_hint": files,
            }
        )
    return bugs


def assign_window(bug: dict) -> int:
    bug_id = bug["bug_id"]
    for window, bug_ids in WORKER_BUG_IDS.items():
        if bug_id in bug_ids:
            return window
    raise ValueError(f"Unassigned bug {bug_id}")


def validate_bug_assignments(bugs: list[dict]) -> None:
    assigned_bug_ids = set()
    expected_bug_ids = {bug["bug_id"] for bug in bugs}

    for window, bug_ids in WORKER_BUG_IDS.items():
        overlap = assigned_bug_ids.intersection(bug_ids)
        if overlap:
            raise ValueError(f"Duplicate bug assignment in window {window}: {sorted(overlap)}")
        assigned_bug_ids.update(bug_ids)

    missing = expected_bug_ids - assigned_bug_ids
    if missing:
        raise ValueError(f"Missing bug assignments: {sorted(missing)}")

    extra = assigned_bug_ids - expected_bug_ids
    if extra:
        raise ValueError(f"Unknown bug assignments: {sorted(extra)}")
