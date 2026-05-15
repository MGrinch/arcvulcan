from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / 'tools' / 'harness_session.py'


def _run_harness(tmp_path: Path, *, run_id: str, env_overrides: dict[str, str], extra_args: list[str] | None = None) -> dict:
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['DAEDALUS_RUNS_DIR'] = str(tmp_path / 'runs')
    env.update(env_overrides)
    cmd = [
        sys.executable,
        str(HARNESS),
        '--issue',
        'ISSUE-20260314-032',
        '--max-turns',
        '2',
        '--run-id',
        run_id,
    ]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report_path = tmp_path / 'runs' / run_id / 'session_report.json'
    with report_path.open('r', encoding='utf-8') as fh:
        return json.load(fh)



def _teach_reground_flags(event_doc: dict) -> list[bool]:
    turns = event_doc['payload']['session_report']['turns']
    return [bool(turn['teach']['prompt_meta']['protocol_regrounded']) for turn in turns]



def test_env_selected_reground_cadence_changes_live_harness_turns(tmp_path: Path) -> None:
    default_doc = _run_harness(
        tmp_path / 'default',
        run_id='bug32-default',
        env_overrides={},
    )
    env_doc = _run_harness(
        tmp_path / 'env',
        run_id='bug32-env-every-1',
        env_overrides={'DAEDALUS_PROTOCOL_REGROUND_EVERY': '1'},
    )

    assert _teach_reground_flags(default_doc) == [True, False]
    assert _teach_reground_flags(env_doc) == [True, True]



def test_cli_reground_override_still_wins_over_env_selected_cadence(tmp_path: Path) -> None:
    doc = _run_harness(
        tmp_path,
        run_id='bug32-cli-override',
        env_overrides={'DAEDALUS_PROTOCOL_REGROUND_EVERY': '1'},
        extra_args=['--protocol-reground-every', '0'],
    )

    assert _teach_reground_flags(doc) == [True, False]
