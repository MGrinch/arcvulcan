from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class Bug20RedteamPoisonSuiteTests(unittest.TestCase):
    def test_requires_grounding_markers_when_requested(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(repo_root)
        cmd = [sys.executable, "tools/redteam_rag_poisoning_suite.py", "--issue", "ISSUE-TEST-BUG20", "--seed", "1337"]

        proc = subprocess.run(cmd, cwd=repo_root, env=env, capture_output=True, text=True)

        self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
        self.assertIn("FAIL:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
