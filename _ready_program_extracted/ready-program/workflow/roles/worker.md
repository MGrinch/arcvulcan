# Worker Role

Use this role for windows `1` to `15`.

Workflow:

1. Load your window entry from `workflow/config/windows.json`.
2. Load `workflow/shared/operating-rules.md`, `workflow/shared/package-format.md`, `workflow/shared/cycle-reset.md`, `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`, your queue file, and your state file.
3. Run `workflow/scripts/start_window_turn.ps1 -Window <N> -AutoApplySeed`.
4. If the returned status is not `ready`, stop and use the returned reply contract.
5. Run `workflow/scripts/get_bug_section.ps1 -BugId <BUG-ID>`.
6. Read the matching queue item metadata and use all of it: `true_north`, `queue_intent`, `merge_style`, `preflight_reads`, `delivery_standard`, `mission`, `implementation_nexus`, and `acceptance_focus`.
7. Fix exactly that one bug with a robust solution that fits the window's assigned area, the queue doctrine, and the North Star.
8. Prefer implementations that make the resulting feature easier to trust, operate, support, and commercialize instead of narrowly masking the failure.
9. Finish with `workflow/scripts/complete_window_turn.ps1 -Window <N> -ItemId <BUG-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any>`.
10. Reply with the explicit absolute filesystem path to the package directory only.

If the queue is exhausted, reply `WINDOW NN COMPLETE`.
