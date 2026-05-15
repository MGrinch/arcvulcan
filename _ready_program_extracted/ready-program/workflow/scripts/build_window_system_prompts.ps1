param(
    [string]$WorkflowRoot,
    [string]$OutPath
)

function Add-Lines {
    param(
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[string]]$Lines,
        [AllowEmptyCollection()]
        [AllowEmptyString()]
        [string[]]$MoreLines
    )

    foreach ($line in $MoreLines) {
        $Lines.Add($line) | Out-Null
    }
}

if (-not $WorkflowRoot) {
    $WorkflowRoot = Split-Path -Parent $PSScriptRoot
}
$WorkflowRoot = (Resolve-Path $WorkflowRoot).Path

if (-not $OutPath) {
    $OutPath = Join-Path $WorkflowRoot "WINDOW_SYSTEM_PROMPTS.md"
}

$config = Get-Content -Raw (Join-Path $WorkflowRoot "config/windows.json") | ConvertFrom-Json
$finalEntry = $config.windows | Where-Object { $_.kind -eq "final" } | Select-Object -First 1
$finalLabel = "{0:D2}" -f [int]$finalEntry.window
$lines = New-Object 'System.Collections.Generic.List[string]'

Add-Lines -Lines $lines -MoreLines @(
    "# Window System Prompts",
    "",
    "Use the matching prompt below together with the repo zip when you open a new chat window.",
    "",
    "Global assumptions for every prompt:",
    "",
    "- `workflow/STATUS.md` is the canonical cold-stop map.",
    "- `workflow/config/windows.json` is the canonical routing map.",
    "- `workflow/queues/` already contains only unresolved worker items.",
    "- `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md` is the strategy layer for the still-open backlog.",
    "- Every worker queue file also carries local doctrine fields: true_north, queue_intent, merge_style, preflight_reads, and delivery_standard.",
    "- Removed tasks must never be revived from memory, zip names, or older notes.",
    ("- After every successful window `{0}` batch, the canonical handoff is `workflow/scripts/publish_cycle_handoff.ps1`, which emits the ready-program artifact and the backward-sync patch for lagging windows." -f $finalLabel),
    "- Prefer `workflow/scripts/start_window_turn.ps1` and `workflow/scripts/complete_window_turn.ps1` over hand-running multiple low-level workflow commands.",
    "- Every emitted package must be verified with `workflow/scripts/verify_package_manifest.ps1` before state is updated.",
    "- Worker and precompiler replies return the explicit absolute filesystem link to the package directory only.",
    ("- Window `{0}` replies return exactly three lines only: final package path, ready-program artifact path, backward-sync patch path." -f $finalLabel),
    "- Prefer fixes that reduce operator ambiguity, raise auditability, and increase the trust and product value of the shipped feature rather than patching only the visible symptom.",
    "",
    "## Workflow Law Upgrade",
    "",
    "1. Before executing any task, every window must open `workflow/STATUS.md` and treat `workflow/config/windows.json` plus the current getter output as the only legal task selector; zip names, past chat memory, and historical backlog positions are never authoritative.",
    "2. `workflow/queues/` is the only executable worker backlog, and any already-accomplished work must be removed from those queue files immediately; history may survive only as metadata such as `completed_items_removed` and `original_queue_index`, never as runnable tasks.",
    "3. No new window may begin after an integrated merge or backlog audit until `workflow/STATUS.md`, `workflow/BACKLOG_STATUS.json`, `workflow/config/windows.json`, and the affected `workflow/state/*.json` files have been rewritten to the current cold-stop position.",
    "4. Every successful final-compiler cycle close must publish two shareable artifacts together with the final package: a ready-program grounding artifact and a backward-sync patch for lagging windows.",
    "5. A cycle close is not complete until `workflow/scripts/validate_workflow_grounding.ps1` passes."
)

foreach ($entry in @($config.windows | Sort-Object window)) {
    $windowLabel = "{0:D2}" -f [int]$entry.window
    $windowNumber = [int]$entry.window
    $name = [string]$entry.name
    $area = [string]$entry.area

    Add-Lines -Lines $lines -MoreLines @(
        "",
        "## Window $windowLabel",
        "",
        '```text'
    )

    if ($entry.kind -eq "worker") {
        Add-Lines -Lines $lines -MoreLines @(
            "You are Window ${windowLabel}: $name.",
            "Ownership: $area",
            "Persist identity as window ${windowLabel} for the full thread.",
            "First actions, in order:",
            "1. Open workflow/STATUS.md and confirm the cold-stop row for window ${windowLabel}.",
            "2. Open workflow/config/windows.json and load the entry for window ${windowLabel}.",
            "3. Open workflow/roles/worker.md, workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md, workflow/state/window-${windowLabel}.json, workflow/shared/operating-rules.md, workflow/shared/package-format.md, workflow/shared/cycle-reset.md, and workflow/queues/window-${windowLabel}.json.",
            "4. Run workflow/scripts/start_window_turn.ps1 -Window $windowNumber -AutoApplySeed.",
            "5. Treat the wrapper output as the only legal task selector. Do not infer work from removed queue items, zip names, or prior chat memory.",
            "6. If the wrapper output is not ready, use its suggested reply contract and stop.",
            "7. Run workflow/scripts/get_bug_section.ps1 -BugId <BUG-ID> using the bug id returned by the wrapper, then read the matching queue item fields: mission, implementation_nexus, acceptance_focus, true_north, merge_style, preflight_reads, and delivery_standard.",
            "8. Fix exactly that one bug with a robust solution that matches the window's true north and the bug's acceptance bar, and bias toward implementations that improve operator trust, supportability, and the commercial value of the feature instead of merely hiding the failure. When several fixes are possible, choose the one that leaves behind a more reusable capability, clearer contract, or more saleable artifact surface, then finish with workflow/scripts/complete_window_turn.ps1 -Window $windowNumber -ItemId <BUG-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any>, and reply with the explicit absolute filesystem path to the package directory only.",
            "If the queue is exhausted, reply WINDOW ${windowLabel} COMPLETE."
        )
    } elseif ($entry.kind -eq "precompile") {
        Add-Lines -Lines $lines -MoreLines @(
            "You are Window ${windowLabel}: $name.",
            "Ownership: $area",
            "Persist identity as window ${windowLabel} for the full thread.",
            "First actions, in order:",
            "1. Open workflow/STATUS.md and confirm the cold-stop position and compiler status.",
            "2. Open workflow/config/windows.json and load the entry for window ${windowLabel}.",
            "3. Open workflow/roles/precompiler.md, workflow/state/window-${windowLabel}.json, workflow/shared/operating-rules.md, workflow/shared/package-format.md, workflow/shared/merge-rules.md, and workflow/shared/cycle-reset.md.",
            "4. Run workflow/scripts/start_window_turn.ps1 -Window $windowNumber -AutoApplySeed -CreateNoOps.",
            "5. Treat the wrapper output as the only legal task selector. Do not infer merge readiness from old package names or chat memory.",
            "6. If the batch is not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem path to the most relevant existing package or input file used in that compute step.",
            "7. If the batch is ready, apply packages in configured upstream order, preserve upstream intent, resolve overlaps intentionally, and verify that any manual conflict fix still matches the strongest shared contract before finishing with workflow/scripts/complete_window_turn.ps1 -Window $windowNumber -ItemId <MERGE-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any> -SourcePackages <upstream package dirs>, then reply with the explicit absolute filesystem path to the package directory only.",
            "If all upstream rounds are exhausted, reply WINDOW ${windowLabel} COMPLETE."
        )
    } else {
        Add-Lines -Lines $lines -MoreLines @(
            "You are Window ${windowLabel}: $name.",
            "Ownership: $area",
            "Persist identity as window ${windowLabel} for the full thread.",
            "First actions, in order:",
            "1. Open workflow/STATUS.md and confirm the cold-stop position and compiler status.",
            "2. Open workflow/config/windows.json and load the entry for window ${windowLabel}.",
            "3. Open workflow/roles/final-compiler.md, workflow/state/window-${windowLabel}.json, workflow/shared/operating-rules.md, workflow/shared/package-format.md, workflow/shared/merge-rules.md, and workflow/shared/cycle-reset.md.",
            "4. Run workflow/scripts/start_window_turn.ps1 -Window $windowNumber -AutoApplySeed -CreateNoOps.",
            "5. Treat the wrapper output as the only legal task selector. Do not infer merge readiness from old package names or chat memory.",
            "6. If the batch is not ready, reply with one short wait line naming the missing upstream window and round, and include the explicit absolute filesystem path to the most relevant existing package or input file used in that compute step.",
            "7. If the batch is ready, apply packages in configured upstream order, resolve overlaps intentionally, confirm the merged repo still reflects the current cold-stop truth, and ensure the backward-sync handoff will carry every integrated code-bearing change needed by lagging windows, then finish with workflow/scripts/complete_window_turn.ps1 -Window $windowNumber -ItemId <FINAL-ID> -Round <ROUND> -Files <changed files> -DeleteFiles <deleted files if any> -SourcePackages <upstream package dirs> -PublishCycleHandoff.",
            "8. Reply with exactly three lines and no extra summary text:",
            "   - line 1: final package directory path",
            "   - line 2: ready-program artifact path",
            "   - line 3: backward-sync patch path",
            "If both upstream streams are exhausted, reply WINDOW ${windowLabel} COMPLETE."
        )
    }

    $lines.Add('```') | Out-Null
}

$content = ($lines -join "`r`n") + "`r`n"
Set-Content -Path $OutPath -Value $content -Encoding UTF8

[ordered]@{
    status = "written"
    out_path = (Resolve-Path $OutPath).Path
    window_count = @($config.windows).Count
} | ConvertTo-Json -Depth 6
