from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_and_get_dir(cmd: list[str], env: dict[str, str]) -> Path:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)
    lines = [ln.strip() for ln in (proc.stdout or '').splitlines() if 'wrote outputs to ' in ln]
    assert lines, proc.stdout + proc.stderr
    run_dir = Path(lines[-1].split('wrote outputs to ', 1)[1].strip())
    assert run_dir.is_dir(), run_dir
    return run_dir


def test_coverage_gate_run_json_marks_nondeterministic(tmp_path: Path) -> None:
    env = dict(os.environ)
    env['DAEDALUS_RUNS_DIR'] = str(tmp_path / 'runs')

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            'tools/coverage_gate.py',
            '--issue',
            'ISSUE-20260315-155',
            '--seed',
            '155',
            '--min-line',
            '0',
            '--min-branch',
            '0',
        ],
        env,
    )

    run_meta = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    assert run_meta['deterministic'] is False



def test_ci_gate_run_json_marks_nondeterministic(tmp_path: Path) -> None:
    env = dict(os.environ)
    env['DAEDALUS_RUNS_DIR'] = str(tmp_path / 'runs')

    run_dir = _run_and_get_dir(
        [
            sys.executable,
            'tools/ci_gate.py',
            '--issue',
            'ISSUE-20260315-155',
            '--seed',
            '155',
            '--max-turns',
            '1',
            '--step-timeout',
            '30',
        ],
        env,
    )

    run_meta = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    assert run_meta['deterministic'] is False
