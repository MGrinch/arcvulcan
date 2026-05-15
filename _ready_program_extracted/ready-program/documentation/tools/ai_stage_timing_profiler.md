# stage_timing_profiler

Profiles rough timings for key stages:

- prompt build (including optional grounding)
- tutor backend generation
- mirror generation (when enabled)

## Usage

```bash
python tools/stage_timing_profiler.py --issue ISSUE-YYYYMMDD-NNN
```

## Outputs

- `runs/<new_run_id>/stage_timing_report.json`

Exit codes:
- `0` PASS
- `1` FAIL