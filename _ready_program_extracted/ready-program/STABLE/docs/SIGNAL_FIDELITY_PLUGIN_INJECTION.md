# Signal Fidelity Plugin Injection (Option A)

**Goal:** reuse pieces of the older “Signal Fidelity” code **without** shipping the whole archive or adding weight.

## What gets shipped (lean)
- `signal_fidelity_src/signal_fidelity_manifest.json`
- `signal_fidelity_src/signal_fidelity_filelist.txt`
- empty plugin folder `signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/`

## What does NOT get shipped (lean)
- the `.rar` archive and any extracted runtime junk

## How to use
1) On your PC, extract the archive with 7-Zip into:
   `signal_fidelity_src/XYZGL_SIGNAL_FIDELITY_002_ASSEMBLED/`

2) List files:
   `python tools/signal_fidelity_port.py --list`

3) Copy only what you want into `tools/` or `xyzgl/`:
   `python tools/signal_fidelity_port.py --copy core.py --to tools/`
