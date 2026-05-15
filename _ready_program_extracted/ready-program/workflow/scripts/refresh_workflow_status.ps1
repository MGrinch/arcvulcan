param()

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$workerEntries = @($config.windows | Where-Object { $_.kind -eq "worker" } | Sort-Object window)
$precompilerEntries = @($config.windows | Where-Object { $_.kind -eq "precompile" } | Sort-Object window)
$finalEntry = $config.windows | Where-Object { $_.kind -eq "final" } | Select-Object -First 1
$cycleSeedPath = Join-Path $workflowRoot "state/cycle-seed.json"
$cycleSeed = $null
if (Test-Path -LiteralPath $cycleSeedPath) {
    $cycleSeed = Get-Content -Raw $cycleSeedPath | ConvertFrom-Json
}

$workerRows = @()
$compilerRows = @()
$implementedTotal = 0
$remainingTotal = 0
$totalItems = 0

foreach ($entry in $workerEntries) {
    $queuePath = Join-Path $workflowRoot $entry.queue_file
    $statePath = Join-Path $workflowRoot $entry.state_file

    $queue = Get-Content -Raw $queuePath | ConvertFrom-Json
    $state = Get-Content -Raw $statePath | ConvertFrom-Json

    $queueItems = @($queue.items)
    $completedRemoved = if ($queue.PSObject.Properties.Name -contains "completed_items_removed") { [int]$queue.completed_items_removed } else { 0 }
    $completedActive = if ($state.PSObject.Properties.Name -contains "completed_count") { [int]$state.completed_count } else { 0 }
    $completedActive = [Math]::Min($completedActive, $queueItems.Count)

    $doneCount = $completedRemoved + $completedActive
    $remainingCount = $queueItems.Count - $completedActive
    $windowTotal = $doneCount + $remainingCount

    $implementedTotal += $doneCount
    $remainingTotal += $remainingCount
    $totalItems += $windowTotal

    $nextItem = $null
    if ($completedActive -lt $queueItems.Count) {
        $nextItem = $queueItems[$completedActive]
    }

    $nextBug = $null
    $nextTitle = $null
    if ($nextItem) {
        $nextBug = [string]$nextItem.bug_id
        $nextTitle = [string]$nextItem.title
    }

    $workerRows += [pscustomobject]@{
        window = [int]$entry.window
        name = [string]$entry.name
        done_count = $doneCount
        remaining_count = $remainingCount
        total_items = $windowTotal
        queue_file = [string]$entry.queue_file
        next_bug = $nextBug
        next_title = $nextTitle
    }
}

foreach ($entry in @($precompilerEntries + @($finalEntry))) {
    if (-not $entry) {
        continue
    }
    $statePath = Join-Path $workflowRoot $entry.state_file
    $state = Get-Content -Raw $statePath | ConvertFrom-Json
    $compilerRows += [pscustomobject]@{
        window = [int]$entry.window
        kind = [string]$entry.kind
        name = [string]$entry.name
        round = if ($state.PSObject.Properties.Name -contains "current_round") { [int]$state.current_round } else { 1 }
        upstreams = if ($entry.PSObject.Properties.Name -contains "upstreams") { @($entry.upstreams) } else { @() }
    }
}

$implementedPct = if ($totalItems -gt 0) { [Math]::Round(($implementedTotal / $totalItems) * 100, 1) } else { 100.0 }
$remainingPct = if ($totalItems -gt 0) { [Math]::Round(($remainingTotal / $totalItems) * 100, 1) } else { 0.0 }
$activeCycleValue = if ($cycleSeed) { [int]$cycleSeed.active_cycle } else { 0 }
$activeWorkerRound = 1
$compilerRound = 1
$precompilerLabel = (@($precompilerEntries | ForEach-Object { "{0:D2}" -f [int]$_.window }) -join ", ")
$finalLabel = if ($finalEntry) { "{0:D2}" -f [int]$finalEntry.window } else { "??" }

$workflowStage = if ($cycleSeed -and $cycleSeed.seed_package_dir) {
    "cycle-$([int]$cycleSeed.active_cycle)-unresolved-backlog"
} else {
    "canonical-unresolved-backlog"
}

$statusLines = @(
    "# Workflow Status",
    "",
    "This repo is aligned to the unresolved backlog that matches the current integrated code snapshot.",
    "",
    "- Audited UTC: $((Get-Date).ToUniversalTime().ToString('o'))",
    "- Active cycle: $activeCycleValue",
    "- Implemented worker items already present: $implementedTotal / $totalItems ($implementedPct%)",
    "- Remaining active worker backlog: $remainingTotal / $totalItems ($remainingPct%)",
    ('- Exact restart point: the next execution begins at worker round {0} on the canonical unresolved backlog in `workflow/queues/`.' -f $activeWorkerRound),
    "- Compiler status: precompilers $precompilerLabel and final $finalLabel are reset to round $compilerRound and should wait for fresh worker packages from the unresolved backlog.",
    "",
    "## Cold-Stop Position",
    ""
)

foreach ($row in $workerRows) {
    if ($row.remaining_count -gt 0) {
        $statusLines += "- Window {0:D2}: {1}/{2} already done, {3} left. Next bug: {4} - {5}" -f $row.window, $row.done_count, $row.total_items, $row.remaining_count, $row.next_bug, $row.next_title
    } else {
        $statusLines += "- Window {0:D2}: {1}/{2} already done, 0 left. Queue complete." -f $row.window, $row.done_count, $row.total_items
    }
}

$statusLines += @(
    "",
    "## Compiler Topology",
    ""
)

foreach ($row in $compilerRows) {
    $statusLines += "- Window {0:D2}: {1} | round {2} | upstreams: {3}" -f $row.window, $row.name, $row.round, (@($row.upstreams) -join ", ")
}

$statusLines += @(
    "",
    "## Canonical Files",
    "",
    '- Live worker queues: `workflow/queues/`',
    '- Workflow summary: `workflow/STATUS.md`',
    '- Machine-readable status: `workflow/BACKLOG_STATUS.json`',
    '- Window routing config: `workflow/config/windows.json`',
    '- Cycle handoff state: `workflow/state/cycle-seed.json`',
    '- Execution intelligence: `workflow/UNRESOLVED_EXECUTION_INTELLIGENCE.md`',
    '- Fast path wrappers: `workflow/scripts/start_window_turn.ps1` and `workflow/scripts/complete_window_turn.ps1`'
)

$statusPath = Join-Path $workflowRoot "STATUS.md"
$statusLines -join "`r`n" | Set-Content -Path $statusPath -Encoding UTF8

$cycleSeedPayload = $null
if ($cycleSeed) {
    $cycleSeedPayload = [ordered]@{
        active_cycle = [int]$cycleSeed.active_cycle
        seed_package_dir = $cycleSeed.seed_package_dir
        seed_source_window = $cycleSeed.seed_source_window
        seed_round = $cycleSeed.seed_round
        seed_kind = $cycleSeed.seed_kind
        seed_prepared_utc = $cycleSeed.seed_prepared_utc
        seed_source_final_package_dir = $cycleSeed.seed_source_final_package_dir
        seed_backward_sync_dir = $cycleSeed.seed_backward_sync_dir
        seed_backward_sync_zip = $cycleSeed.seed_backward_sync_zip
        seed_ready_repo_dir = $cycleSeed.seed_ready_repo_dir
        seed_ready_repo_zip = $cycleSeed.seed_ready_repo_zip
    }
}

$backlogPayload = [ordered]@{
    audited_utc = (Get-Date).ToUniversalTime().ToString("o")
    workflow_stage = $workflowStage
    summary = [ordered]@{
        total_worker_items = $totalItems
        implemented_items = $implementedTotal
        remaining_items = $remainingTotal
        implemented_percent = $implementedPct
        active_worker_round = $activeWorkerRound
        compiler_round = $compilerRound
        active_cycle = $activeCycleValue
    }
    topology = [ordered]@{
        worker_windows = @($workerEntries | ForEach-Object { [int]$_.window })
        precompiler_windows = @($precompilerEntries | ForEach-Object { [int]$_.window })
        final_window = if ($finalEntry) { [int]$finalEntry.window } else { $null }
    }
    notes = @(
        "workflow/queues/ is the only canonical worker backlog and contains only unresolved items for the current cycle.",
        "Prefer start_window_turn.ps1 and complete_window_turn.ps1 for the standardized fast path.",
        ("After each successful window {0:D2} cycle close, publish_cycle_handoff.ps1 must emit a ready-program artifact and a backward-sync patch before the next cycle begins." -f [int]$finalEntry.window),
        "Cycle seed state records the backward-sync patch that lagging windows must apply before they continue."
    )
    cycle_seed = $cycleSeedPayload
    windows = @($workerRows)
    compilers = @($compilerRows)
} | ConvertTo-Json -Depth 10

$backlogPath = Join-Path $workflowRoot "BACKLOG_STATUS.json"
$backlogPayload | Set-Content -Path $backlogPath -Encoding UTF8

[ordered]@{
    status_file = $statusPath
    backlog_file = $backlogPath
    summary = [ordered]@{
        total_worker_items = $totalItems
        implemented_items = $implementedTotal
        remaining_items = $remainingTotal
        active_cycle = $activeCycleValue
    }
} | ConvertTo-Json -Depth 8
