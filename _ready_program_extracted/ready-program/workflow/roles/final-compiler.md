# Final Compiler Role

Use this role for window `18`.

Workflow:

1. Load your window entry from `workflow/config/windows.json`.
2. Load `workflow/shared/operating-rules.md`, `workflow/shared/package-format.md`, `workflow/shared/merge-rules.md`, `workflow/shared/cycle-reset.md`, and your state file.
3. Run `workflow/scripts/start_window_turn.ps1 -Window 18 -AutoApplySeed -CreateNoOps`.
4. If the batch is not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem path to the most relevant existing package or input file used in that compute step.
5. If the batch is ready, apply the listed packages with `workflow/scripts/apply_patch_package.ps1`.
6. Resolve overlaps intentionally and confirm the merged repo reflects the current cold-stop truth before packaging.
7. Prefer final merges that strengthen the ship-ready program, the handoff artifacts, and the operator's confidence in what was truly integrated.
8. Finish with `workflow/scripts/complete_window_turn.ps1 -Window 18 -ItemId <FINAL-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any> -SourcePackages <upstream package dirs> -PublishCycleHandoff`.
9. Reply with exactly three lines and no extra summary text:
   - final package directory
   - ready-program artifact path
   - backward-sync patch path

If both upstream precompiler streams are exhausted, reply `WINDOW 18 COMPLETE`.
