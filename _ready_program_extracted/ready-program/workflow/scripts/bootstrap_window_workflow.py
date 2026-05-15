from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from window_workflow_layout import (
    REPORT_EXPECTED_BUG_COUNT,
    WINDOWS,
    assign_window,
    parse_bug_sections,
    validate_bug_assignments,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def build_queue_markdown(window_entry: dict, report_name: str, items: list[dict]) -> str:
    lines = [
        f"# Window {window_entry['window']:02d} Queue",
        "",
        f"- Name: {window_entry['name']}",
        f"- Area: {window_entry['area']}",
        f"- Total bugs: {len(items)}",
        f"- Local report: workflow/source/{report_name}",
        "- Full bug lookup: run `workflow/scripts/get_bug_section.ps1 -BugId BUG-XXX`",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(
            f"{index}. {item['bug_id']} | phase {item['phase']} | {item['severity']} | {item['title']}"
        )
        if item["files_hint"]:
            lines.append(f"   files: {', '.join(item['files_hint'])}")
    return "\n".join(lines)


def initial_state(window_entry: dict, total_items: int | None = None) -> dict:
    payload = {
        "window": window_entry["window"],
        "kind": window_entry["kind"],
        "name": window_entry["name"],
        "area": window_entry["area"],
        "status": "idle",
        "last_package_dir": None,
        "last_seeded_cycle": 0,
        "last_seed_package_dir": None,
        "history": [],
    }
    if window_entry["kind"] == "worker":
        payload["completed_count"] = 0
        payload["current_round"] = 1
        payload["current_item"] = None
        payload["total_items"] = total_items
    else:
        payload["completed_rounds"] = 0
        payload["current_round"] = 1
        payload["upstreams"] = window_entry["upstreams"]
    return payload


def initial_cycle_seed_state() -> dict:
    return {
        "active_cycle": 1,
        "seed_package_dir": None,
        "seed_source_window": None,
        "seed_round": None,
        "seed_kind": None,
        "seed_prepared_utc": None,
        "seed_source_final_package_dir": None,
        "seed_backward_sync_dir": None,
        "seed_backward_sync_zip": None,
        "seed_ready_repo_dir": None,
        "seed_ready_repo_zip": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Path to the bug report markdown file.")
    parser.add_argument("--force", action="store_true", help="Overwrite generated workflow assets.")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    workflow_root = script_path.parent.parent
    report_source = Path(args.report).resolve()
    if not report_source.exists():
        raise SystemExit(f"Report not found: {report_source}")

    protected_paths = [
        workflow_root / "config" / "windows.json",
        workflow_root / "source" / report_source.name,
        workflow_root / "state" / "cycle-seed.json",
    ]
    if not args.force:
        for path in protected_paths:
            if path.exists():
                raise SystemExit(f"Refusing to overwrite existing generated asset without --force: {path}")

    report_target = workflow_root / "source" / report_source.name
    report_target.parent.mkdir(parents=True, exist_ok=True)
    if report_source != report_target:
        shutil.copyfile(report_source, report_target)

    text = report_target.read_text(encoding="utf-8")
    bugs = parse_bug_sections(text)
    if len(bugs) != REPORT_EXPECTED_BUG_COUNT:
        raise SystemExit(
            f"Expected {REPORT_EXPECTED_BUG_COUNT} bug sections, found {len(bugs)}"
        )

    validate_bug_assignments(bugs)

    by_window: dict[int, list[dict]] = {entry["window"]: [] for entry in WINDOWS if entry["kind"] == "worker"}
    for bug in bugs:
        assigned = assign_window(bug)
        by_window[assigned].append(bug)

    write_json(
        workflow_root / "config" / "windows.json",
        {
            "report_file": f"source/{report_source.name}",
            "windows": WINDOWS,
        },
    )
    write_json(workflow_root / "state" / "cycle-seed.json", initial_cycle_seed_state())

    for entry in WINDOWS:
        (workflow_root / entry["output_root"]).mkdir(parents=True, exist_ok=True)
        if entry["kind"] == "worker":
            items = []
            for index, bug in enumerate(by_window[entry["window"]], start=1):
                items.append(
                    {
                        "queue_index": index,
                        "bug_id": bug["bug_id"],
                        "title": bug["title"],
                        "phase": bug["phase"],
                        "severity": bug["severity"],
                        "files_hint": bug["files_hint"],
                    }
                )
            write_json(
                workflow_root / entry["queue_file"],
                {
                    "window": entry["window"],
                    "name": entry["name"],
                    "area": entry["area"],
                    "report_file": f"source/{report_source.name}",
                    "completed_items_removed": 0,
                    "remaining_items": len(items),
                    "items": items,
                    "queue_kind": "full-bootstrap",
                },
            )
            write_text(
                workflow_root / entry["queue_file"].replace(".json", ".md"),
                build_queue_markdown(entry, report_source.name, items),
            )
            write_json(workflow_root / entry["state_file"], initial_state(entry, len(items)))
        else:
            write_json(workflow_root / entry["state_file"], initial_state(entry))

    print(f"Workflow bootstrapped in {workflow_root.parent}")


if __name__ == "__main__":
    main()
