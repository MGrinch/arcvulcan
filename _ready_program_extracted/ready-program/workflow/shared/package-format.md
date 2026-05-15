# Package Format

Every emitted package lives under `workflow/out/window-XX/` and uses this layout:

```text
workflow/out/window-XX/round-YY__ITEM-ID/
  manifest.json
  apply_patch.ps1
  files/
    <repo-relative files copied here>
```

Manifest fields:

- `window`: source window number
- `round`: queue index or merge round
- `item_id`: bug id, merge label, or final label
- `kind`: `worker`, `precompile`, `final`, or `noop`
- `files`: repo-relative files included in `files/`
- `delete_files`: repo-relative files to delete when applying
- `source_packages`: upstream package directories used to build this package
- `created_utc`: UTC timestamp

`apply_patch.ps1` is self-contained. It copies packaged files into a target repo and removes any `delete_files`.

`workflow/scripts/new_patch_package.ps1` infers `kind` from the window role when `-PackageKind` is omitted, so worker windows emit `worker`, precompilers emit `precompile`, and the final compiler emits `final`.

Every window must verify its freshly created package before updating state:

```text
workflow/scripts/verify_package_manifest.ps1 -PackagePath <package dir> ...
```

That verification step checks the manifest, the packaged file layout, and the expected routing metadata for the current window and round.

The preferred fast path is:

- `workflow/scripts/start_window_turn.ps1` to select the legal turn and apply the cycle seed if needed
- `workflow/scripts/complete_window_turn.ps1` to package, verify, update state, and optionally publish the cycle handoff

Cycle handoff artifacts:

- After every successful window `18` batch, `workflow/scripts/publish_cycle_handoff.ps1` emits a handoff folder under `workflow/handoffs/cycle-XX/`.
- That handoff folder contains:
  - `ready-program/` with a full grounded repo snapshot for opening a fresh chat window on the current integrated code
  - `*_ready.zip`, a zipped copy of that grounded repo snapshot
  - `backward-sync-patch/`, a patch package that lagging windows can apply with `workflow/scripts/apply_cycle_seed.ps1`
  - `*_backward-sync.zip`, a zipped copy of that backward-sync patch
  - `workflow-validation.json`, the validation report proving the cycle handoff left the workflow grounding in a coherent state
- The `ready-program/` snapshot is created after the cycle seed and cold-stop files are rewritten, so it reflects the real restart point for the next cycle.
- `workflow/state/cycle-seed.json` records the canonical backward-sync package plus the ready-program artifact paths for the current cycle.
