from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import targeted_sweep as sweep  # noqa: E402


class Bug45TargetedSweepRawPathExtractionTests(unittest.TestCase):
    def test_record_step_extracts_child_run_dir_from_raw_stdout_and_keeps_safe_stdout_tail(self) -> None:
        temp_root = Path(__file__).resolve().parent / ".tmp_bug45_case"
        _cleanup_tree(temp_root)
        temp_root.mkdir(parents=True)
        self.addCleanup(lambda: _cleanup_tree(temp_root))

        run_dir = temp_root / "parent_run"
        child_runs = run_dir / "child_runs"
        child_run = child_runs / "session_a"
        child_run.mkdir(parents=True)
        (child_run / "run.json").write_text("{}", encoding="utf-8")

        raw_stdout = f"PASS: wrote outputs to {child_run}\n"
        safe_stdout = "PASS: wrote outputs to <path>\n"

        step, child_run_dir, expected_seed = sweep._record_step(
            name="harness_session",
            prepared_cmd=[sys.executable, "tools/harness_session.py", "--seed", "17"],
            step_result=(0, raw_stdout, safe_stdout, "step_logs/harness_session.stdout.log"),
            child_runs=child_runs,
            run_dir=run_dir,
        )

        self.assertEqual(step["exit_code"], 0)
        self.assertEqual(step["stdout_tail"], safe_stdout)
        self.assertEqual(step["stdout_log"], "step_logs/harness_session.stdout.log")
        self.assertEqual(step["child_run_dir"], "child_runs/session_a")
        self.assertEqual(child_run_dir, str(child_run.resolve()))
        self.assertEqual(expected_seed, 17)
        self.assertNotIn(str(child_run), str(step["stdout_tail"]))


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
