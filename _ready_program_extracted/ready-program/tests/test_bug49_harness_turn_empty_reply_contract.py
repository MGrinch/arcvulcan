from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / 'tools' / 'harness_turn.py'


def _latest_run_dir(runs_dir: Path) -> Path:
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    assert candidates, 'expected at least one harness_turn run directory'
    return candidates[-1]


def test_harness_turn_fails_fault_empty_backend_even_if_route_turn_falls_back(tmp_path: Path) -> None:
    runs_dir = tmp_path / 'runs'
    proc = subprocess.run(
        [
            sys.executable,
            str(HARNESS_PATH),
            '--issue',
            'ISSUE-20260315-049',
            '--seed',
            '1337',
            '--text',
            'fit-up issue',
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            'DAEDALUS_RUNS_DIR': str(runs_dir),
            'DAEDALUS_TUTOR_BACKEND': 'fault',
            'DAEDALUS_FAULT_MODE': 'empty',
            'DAEDALUS_EXPOSE_BACKEND_ERRORS': '1',
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert 'FAIL: wrote outputs to' in proc.stdout

    run_dir = _latest_run_dir(runs_dir)
    report = json.loads((run_dir / 'turn_report.json').read_text(encoding='utf-8'))
    run_meta = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    summary_text = (run_dir / 'turn_summary.md').read_text(encoding='utf-8')
    turn_result = report['payload']['turn_result']

    assert turn_result['requested_backend'] == 'fault'
    assert turn_result['effective_backend'] == 'stub'
    assert turn_result['backend'] == 'stub'
    assert turn_result['reply'] == ''
    assert turn_result['backend_error'] == 'backend_contract_error: empty tutor reply'
    assert turn_result['exception_type'] == 'BackendContractError'
    assert turn_result['exception_message'] == 'backend_contract_error: empty tutor reply'

    assert run_meta['exit_codes']['1'] == 'FAIL'
    assert '# Turn Summary — FAIL' in summary_text
    assert 'backend_contract_error: empty tutor reply' in summary_text
