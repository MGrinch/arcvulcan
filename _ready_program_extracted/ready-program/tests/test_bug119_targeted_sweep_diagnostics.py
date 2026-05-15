from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import targeted_sweep as sweep  # noqa: E402


class Bug119TargetedSweepTests(unittest.TestCase):
    def test_failure_stdout_keeps_full_detail_when_under_inline_budget(self) -> None:
        lines = [f"line budget exceeded: tools/file_{i:03d}.py" for i in range(31)]
        text = "FAIL:\n" + "\n".join(lines)
        rendered = sweep._report_stdout_text(text, exit_code=1)
        self.assertEqual(rendered, text)
        self.assertIn("tools/file_000.py", rendered)
        self.assertIn("tools/file_030.py", rendered)
        self.assertNotIn("chars omitted", rendered)

    def test_failed_child_step_inlines_child_summary_excerpt(self) -> None:
        root = Path(self.id().replace(".", "_")).resolve()
        # Use a temporary tree underneath the test file's directory to keep paths deterministic.
        temp_root = Path(__file__).resolve().parent / ".tmp_bug119_case"
        if temp_root.exists():
            for child in sorted(temp_root.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            temp_root.rmdir()
        temp_root.mkdir(parents=True)
        self.addCleanup(lambda: _cleanup_tree(temp_root))

        child_run = temp_root / "child_runs" / "doctor_run"
        child_run.mkdir(parents=True)
        (child_run / "run.json").write_text(
            json.dumps(
                {
                    "outputs": [
                        "doctor_report.json",
                        "doctor_summary.md",
                        "run.json",
                    ]
                }
            ),
            encoding="utf-8",
        )
        (child_run / "doctor_report.json").write_text("{}", encoding="utf-8")
        (child_run / "doctor_summary.md").write_text(
            "# Doctor summary\n\n- line budget exceeded: tools/a.py\n- line budget exceeded: tools/b.py\n",
            encoding="utf-8",
        )

        context = sweep._load_child_artifact_context(child_run, run_dir=temp_root)
        rendered = sweep._augment_step_stdout(
            "FAIL: wrote outputs to <path>",
            exit_code=1,
            child_context=context,
        )

        self.assertEqual(context["child_run_dir"], "child_runs/doctor_run")
        self.assertEqual(context["child_summary"], "child_runs/doctor_run/doctor_summary.md")
        self.assertEqual(context["child_report"], "child_runs/doctor_run/doctor_report.json")
        self.assertIn("child_runs/doctor_run/doctor_summary.md", rendered)
        self.assertIn("- line budget exceeded:", rendered)
        self.assertIn("tools<path>", rendered)

    def test_failed_child_step_falls_back_to_report_excerpt_when_summary_missing(self) -> None:
        temp_root = Path(__file__).resolve().parent / ".tmp_bug119_report_only"
        if temp_root.exists():
            _cleanup_tree(temp_root)
        temp_root.mkdir(parents=True)
        self.addCleanup(lambda: _cleanup_tree(temp_root))

        child_run = temp_root / "child_runs" / "fault_run"
        child_run.mkdir(parents=True)
        (child_run / "run.json").write_text(
            json.dumps(
                {
                    "outputs": [
                        "backend_fault_report.json",
                        "run.json",
                    ]
                }
            ),
            encoding="utf-8",
        )
        (child_run / "backend_fault_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "backend_fault_report@1",
                    "overall": "FAIL",
                    "problems": [
                        "router fallback returned malformed result",
                        "stderr exceeded inline budget",
                    ],
                }
            ),
            encoding="utf-8",
        )

        context = sweep._load_child_artifact_context(child_run, run_dir=temp_root)
        rendered = sweep._augment_step_stdout(
            "FAIL: wrote outputs to <path>",
            exit_code=1,
            child_context=context,
        )

        self.assertEqual(context["child_report"], "child_runs/fault_run/backend_fault_report.json")
        self.assertIn("child_runs/fault_run/backend_fault_report.json", rendered)
        self.assertIn("overall: FAIL", rendered)
        self.assertIn("router fallback returned malformed result", rendered)
        self.assertIn("stderr exceeded inline budget", rendered)


def _cleanup_tree(root: Path) -> None:
    if not root.exists():
        return
    for child in sorted(root.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    root.rmdir()


if __name__ == "__main__":
    unittest.main()
