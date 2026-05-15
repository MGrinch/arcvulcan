from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_paths import invalid_runs_override_reason

HARNESS_TURN = REPO_ROOT / 'tools' / 'harness_turn.py'
PROPERTY_FUZZER = REPO_ROOT / 'tools' / 'property_turn_fuzzer.py'


def _run_dirs_snapshot() -> set[str]:
    runs_root = REPO_ROOT / 'runs'
    if not runs_root.exists():
        return set()
    return {p.name for p in runs_root.iterdir() if p.is_dir()}


@pytest.mark.parametrize('override_value', ['not-a-dir', 'nested/not-a-dir'])
def test_invalid_runs_override_reason_rejects_non_directory_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override_value: str) -> None:
    target = tmp_path / override_value
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('not a directory', encoding='utf-8')
    monkeypatch.setenv('DAEDALUS_RUNS_DIR', str(target))

    reason = invalid_runs_override_reason()

    assert reason is not None
    assert 'invalid DAEDALUS_RUNS_DIR override' in reason
    assert str(target) in reason


@pytest.mark.parametrize(
    ('tool_path', 'extra_args'),
    [
        (HARNESS_TURN, ['--text', 'fit-up issue']),
        (PROPERTY_FUZZER, ['--cases', '2', '--max-len', '8']),
    ],
)
def test_phase4_tools_fail_closed_on_invalid_runs_override(
    tmp_path: Path,
    tool_path: Path,
    extra_args: list[str],
) -> None:
    invalid_target = tmp_path / 'not-a-dir'
    invalid_target.write_text('still a file', encoding='utf-8')
    before = _run_dirs_snapshot()

    proc = subprocess.run(
        [sys.executable, str(tool_path), '--issue', 'ISSUE-20260315-060', '--seed', '1337', *extra_args],
        cwd=REPO_ROOT,
        env={**os.environ, 'DAEDALUS_RUNS_DIR': str(invalid_target)},
        capture_output=True,
        text=True,
        check=False,
    )

    after = _run_dirs_snapshot()
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2, combined
    assert 'INCOMPLETE: invalid DAEDALUS_RUNS_DIR override' in combined
    assert before == after, 'invalid explicit override should not silently allocate a fallback run dir'
