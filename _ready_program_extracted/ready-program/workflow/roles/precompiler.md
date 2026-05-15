# Precompiler Role

Use this role for windows `16` and `17`.

Workflow:

1. Load your window entry from `workflow/config/windows.json`.
2. Load `workflow/shared/operating-rules.md`, `workflow/shared/package-format.md`, `workflow/shared/merge-rules.md`, `workflow/shared/cycle-reset.md`, and your state file.
3. Run `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed -CreateNoOps`.
4. If the batch is not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem path to the most relevant existing package or input file used in that compute step.
5. If the batch is ready, apply the listed packages with `workflow/scripts/apply_patch_package.ps1`.
6. Preserve configured upstream order and resolve overlaps intentionally; favor the stronger shared contract instead of whichever patch arrived later.
7. If you had to resolve any overlap manually, include those files in the final package file list.
8. Prefer merges that make the resulting stream more supportable, auditable, and product-grade instead of merely conflict-free.
9. Finish with `workflow/scripts/complete_window_turn.ps1 -Window <N> -ItemId <MERGE-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any> -SourcePackages <upstream package dirs>`.
10. Reply with the explicit absolute filesystem path to the package directory only.

If all upstream rounds are exhausted, reply `WINDOW NN COMPLETE`.
