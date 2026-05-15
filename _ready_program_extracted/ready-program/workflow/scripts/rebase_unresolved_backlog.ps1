param()

function Set-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Object,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        $Value
    )

    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        Add-Member -InputObject $Object -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Get-HistoryEntriesFromOutputRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot,
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Entry
    )

    if (-not ($Entry.PSObject.Properties.Name -contains "output_root")) {
        return @()
    }

    $outputRoot = Join-Path $WorkflowRoot $Entry.output_root
    if (-not (Test-Path -LiteralPath $outputRoot)) {
        return @()
    }

    $manifests = Get-ChildItem -LiteralPath $outputRoot -Recurse -Filter manifest.json | Sort-Object FullName
    $entries = @()
    foreach ($manifestFile in $manifests) {
        $manifest = Get-Content -Raw $manifestFile.FullName | ConvertFrom-Json
        if ($Entry.kind -eq "worker" -and [string]$manifest.kind -ne "worker") {
            continue
        }
        if ($Entry.kind -in @("precompile", "final") -and [string]$manifest.kind -notin @("precompile", "final", "noop")) {
            continue
        }

        $actionName = "batch-complete"
        if ($Entry.kind -eq "worker") {
            $actionName = "worker-complete"
        }

        $entries += [pscustomobject]@{
            timestamp_utc = [string]$manifest.created_utc
            action = $actionName
            item_id = [string]$manifest.item_id
            round = [int]$manifest.round
            package_dir = (Split-Path -Parent $manifestFile.FullName)
            files = @($manifest.files)
            delete_files = @($manifest.delete_files)
            source_packages = @($manifest.source_packages)
        }
    }

    return @($entries | Sort-Object round, item_id, timestamp_utc)
}

function Add-ArchivedHistorySnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$State,
        [int]$Cycle,
        [object[]]$FallbackEntries = @()
    )

    $entries = @()
    if ($State.history) {
        $entries = @($State.history)
    }
    $existingArchive = @()
    if ($State.PSObject.Properties.Name -contains "archived_history" -and $State.archived_history) {
        $existingArchive = @($State.archived_history)
    }

    if ($entries.Count -eq 0 -and $existingArchive.Count -eq 0 -and @($FallbackEntries).Count -gt 0) {
        $entries = @($FallbackEntries)
    }

    if ($entries.Count -eq 0) {
        $State.history = @()
        return $State
    }

    $archive = @($existingArchive)

    $archive += [pscustomobject]@{
        archived_utc = (Get-Date).ToUniversalTime().ToString("o")
        reason = "cycle-rebase"
        cycle = $Cycle
        entries = @($entries)
    }

    Set-ObjectProperty -Object $State -Name "archived_history" -Value $archive
    Set-ObjectProperty -Object $State -Name "history" -Value @()
    return $State
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$cycleSeedPath = Join-Path $workflowRoot "state/cycle-seed.json"
$cycleState = $null
if (Test-Path -LiteralPath $cycleSeedPath) {
    $cycleState = Get-Content -Raw $cycleSeedPath | ConvertFrom-Json
}
$activeCycle = if ($cycleState) { [int]$cycleState.active_cycle } else { 0 }

$workerResults = @()
foreach ($entry in @($config.windows | Where-Object { $_.kind -eq "worker" } | Sort-Object window)) {
    $queuePath = Join-Path $workflowRoot $entry.queue_file
    $statePath = Join-Path $workflowRoot $entry.state_file

    $queue = Get-Content -Raw $queuePath | ConvertFrom-Json
    $state = Get-Content -Raw $statePath | ConvertFrom-Json

    $items = @($queue.items)
    $completedCount = 0
    if ($state.PSObject.Properties.Name -contains "completed_count") {
        $completedCount = [Math]::Min([int]$state.completed_count, $items.Count)
    }

    $remaining = @()
    if ($completedCount -lt $items.Count) {
        $remaining = @($items[$completedCount..($items.Count - 1)])
    }

    for ($i = 0; $i -lt $remaining.Count; $i++) {
        $remaining[$i].queue_index = $i + 1
    }

    $removedPrior = 0
    if ($queue.PSObject.Properties.Name -contains "completed_items_removed") {
        $removedPrior = [int]$queue.completed_items_removed
    }

    Set-ObjectProperty -Object $queue -Name "completed_items_removed" -Value ($removedPrior + $completedCount)
    Set-ObjectProperty -Object $queue -Name "remaining_items" -Value @($remaining).Count
    Set-ObjectProperty -Object $queue -Name "rebased_utc" -Value ((Get-Date).ToUniversalTime().ToString("o"))
    Set-ObjectProperty -Object $queue -Name "items" -Value @($remaining)
    $queue | ConvertTo-Json -Depth 10 | Set-Content -Path $queuePath -Encoding UTF8

    $fallbackEntries = Get-HistoryEntriesFromOutputRoot -WorkflowRoot $workflowRoot -Entry $entry
    $state = Add-ArchivedHistorySnapshot -State $state -Cycle $activeCycle -FallbackEntries $fallbackEntries
    Set-ObjectProperty -Object $state -Name "completed_count" -Value 0
    Set-ObjectProperty -Object $state -Name "current_round" -Value 1
    Set-ObjectProperty -Object $state -Name "current_item" -Value $null
    Set-ObjectProperty -Object $state -Name "total_items" -Value @($remaining).Count
    Set-ObjectProperty -Object $state -Name "status" -Value $(if (@($remaining).Count -eq 0) { "complete" } else { "ready" })
    Set-ObjectProperty -Object $state -Name "rebased_utc" -Value ((Get-Date).ToUniversalTime().ToString("o"))
    $state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8

    $workerResults += [pscustomobject]@{
        window = [int]$entry.window
        removed_now = $completedCount
        remaining_items = @($remaining).Count
        status = [string]$state.status
    }
}

$compilerResults = @()
foreach ($entry in @($config.windows | Where-Object { $_.kind -in @("precompile", "final") } | Sort-Object window)) {
    $statePath = Join-Path $workflowRoot $entry.state_file
    $state = Get-Content -Raw $statePath | ConvertFrom-Json

    $fallbackEntries = Get-HistoryEntriesFromOutputRoot -WorkflowRoot $workflowRoot -Entry $entry
    $state = Add-ArchivedHistorySnapshot -State $state -Cycle $activeCycle -FallbackEntries $fallbackEntries
    Set-ObjectProperty -Object $state -Name "completed_rounds" -Value 0
    Set-ObjectProperty -Object $state -Name "current_round" -Value 1
    Set-ObjectProperty -Object $state -Name "status" -Value "idle"
    Set-ObjectProperty -Object $state -Name "rebased_utc" -Value ((Get-Date).ToUniversalTime().ToString("o"))
    $state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8

    $compilerResults += [pscustomobject]@{
        window = [int]$entry.window
        kind = [string]$entry.kind
        status = [string]$state.status
    }
}

[ordered]@{
    rebased_utc = (Get-Date).ToUniversalTime().ToString("o")
    workflow_root = $workflowRoot
    active_cycle = $activeCycle
    workers = @($workerResults)
    compilers = @($compilerResults)
} | ConvertTo-Json -Depth 10
