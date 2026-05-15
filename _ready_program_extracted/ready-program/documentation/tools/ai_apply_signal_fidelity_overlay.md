# Apply Signal Fidelity Overlay

Applies the Signal Fidelity overlay into `signal_fidelity_src/` with a **no-overwrite** policy and writes a standard run bundle.

## Default source

By default it uses the shipped extracted overlay directory:

- `signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/`

This repo snapshot does **not** ship the historical `.rar` bundle. If you want to use a RAR archive, provide it explicitly with `--overlay ...rar --allow-external-rar`.

## Usage

```bash
python tools/apply_signal_fidelity_overlay.py --issue ISSUE-YYYYMMDD-NNN
```

### Explicitly force the shipped extracted source

```bash
python tools/apply_signal_fidelity_overlay.py --issue ISSUE-YYYYMMDD-NNN --from-src
```

### Provide a ZIP (pure Python, no external extractor)

```bash
python tools/apply_signal_fidelity_overlay.py --issue ISSUE-YYYYMMDD-NNN --overlay path/to/overlay.zip
```

### Provide an extracted directory (copy)

```bash
python tools/apply_signal_fidelity_overlay.py --issue ISSUE-YYYYMMDD-NNN --overlay path/to/overlay_dir/
```

### Keep the extracted temp directory (debug)

```bash
python tools/apply_signal_fidelity_overlay.py --issue ISSUE-YYYYMMDD-NNN --keep-tmp
```

## Outputs

- `runs/<run_id>/signal_fidelity_apply_report.json`
- `runs/<run_id>/signal_fidelity_apply_summary.md`
- `runs/<run_id>/run.json`

## Exit codes

- `0` PASS
- `1` FAIL
- `2` INCOMPLETE (missing source or missing RAR extractor when using a `.rar`)
