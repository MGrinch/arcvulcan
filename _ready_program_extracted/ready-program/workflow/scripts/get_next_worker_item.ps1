param(
    [Parameter(Mandatory = $true)]
    [int]$Window
)

$workflowRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $workflowRoot "config/windows.json"
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}
if ($entry.kind -ne "worker") {
    throw "Window $Window is not a worker window"
}

$queuePath = Join-Path $workflowRoot $entry.queue_file
$statePath = Join-Path $workflowRoot $entry.state_file
$queue = Get-Content -Raw $queuePath | ConvertFrom-Json
$state = Get-Content -Raw $statePath | ConvertFrom-Json
$cycleSeedPath = Join-Path $workflowRoot "state/cycle-seed.json"
$cycleSeed = $null
if (Test-Path -LiteralPath $cycleSeedPath) {
    $cycleSeed = Get-Content -Raw $cycleSeedPath | ConvertFrom-Json
}

$lastSeededCycle = 0
if ($state.PSObject.Properties.Name -contains "last_seeded_cycle") {
    $lastSeededCycle = [int]$state.last_seeded_cycle
}

if ($cycleSeed -and $cycleSeed.seed_package_dir -and ($lastSeededCycle -lt [int]$cycleSeed.active_cycle)) {
    [ordered]@{
        ready = $false
        status = "seed-required"
        window = $Window
        name = $entry.name
        cycle = [int]$cycleSeed.active_cycle
        seed_package_dir = [string]$cycleSeed.seed_package_dir
        state_file = $statePath
    } | ConvertTo-Json -Depth 8
    exit 0
}

$completedCount = [int]$state.completed_count
$totalCount = @($queue.items).Count

if ($completedCount -ge $totalCount) {
    [ordered]@{
        ready = $false
        status = "complete"
        window = $Window
        name = $entry.name
        total_items = $totalCount
        completed_count = $completedCount
    } | ConvertTo-Json -Depth 8
    exit 0
}

$nextItem = @($queue.items)[$completedCount]
[ordered]@{
    ready = $true
    status = "ready"
    window = $Window
    name = $entry.name
    area = $entry.area
    report_file = Join-Path $workflowRoot $config.report_file
    state_file = $statePath
    queue_file = $queuePath
    round = [int]$nextItem.queue_index
    completed_count = $completedCount
    remaining_count = $totalCount - $completedCount
    item = $nextItem
} | ConvertTo-Json -Depth 8
