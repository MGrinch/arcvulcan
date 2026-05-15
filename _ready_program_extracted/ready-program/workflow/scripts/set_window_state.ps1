param(
    [Parameter(Mandatory = $true)]
    [int]$Window,

    [Parameter(Mandatory = $true)]
    [ValidateSet("worker-complete", "batch-complete")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$ItemId,

    [Parameter(Mandatory = $true)]
    [int]$Round,

    [string]$PackageDir,

    [string[]]$Files = @(),

    [string[]]$DeleteFiles = @(),

    [string[]]$SourcePackages = @()
)

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}

$statePath = Join-Path $workflowRoot $entry.state_file
$state = Get-Content -Raw $statePath | ConvertFrom-Json

$history = @()
if ($state.history) {
    $history = @($state.history)
}
$history += [pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    action = $Action
    item_id = $ItemId
    round = $Round
    package_dir = $PackageDir
    files = @($Files)
    delete_files = @($DeleteFiles)
    source_packages = @($SourcePackages)
}

$state.history = $history
$state.last_package_dir = $PackageDir

if ($Action -eq "worker-complete") {
    $queue = Get-Content -Raw (Join-Path $workflowRoot $entry.queue_file) | ConvertFrom-Json
    $state.completed_count = [int]$Round
    $state.current_round = [int]$Round + 1
    $state.current_item = $null
    if ($Round -ge @($queue.items).Count) {
        $state.status = "complete"
    } else {
        $state.status = "ready"
    }
} else {
    $state.completed_rounds = [int]$Round
    $state.current_round = [int]$Round + 1
    $state.status = "ready"
}

$state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8
$state | ConvertTo-Json -Depth 10
