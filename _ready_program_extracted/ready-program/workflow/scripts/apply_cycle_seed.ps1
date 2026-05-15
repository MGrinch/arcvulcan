param(
    [Parameter(Mandatory = $true)]
    [int]$Window,

    [string]$TargetRepo
)

$workflowRoot = Split-Path -Parent $PSScriptRoot
if (-not $TargetRepo) {
    $TargetRepo = Split-Path -Parent $workflowRoot
}
$TargetRepo = (Resolve-Path $TargetRepo).Path

$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}

$seedStatePath = Join-Path $workflowRoot "state/cycle-seed.json"
if (-not (Test-Path -LiteralPath $seedStatePath)) {
    throw "Missing cycle seed state: $seedStatePath"
}
$seedState = Get-Content -Raw $seedStatePath | ConvertFrom-Json
if (-not $seedState.seed_package_dir) {
    [ordered]@{
        status = "no-seed"
        window = $Window
        target_repo = $TargetRepo
    } | ConvertTo-Json -Depth 8
    exit 0
}

$statePath = Join-Path $workflowRoot $entry.state_file
$state = Get-Content -Raw $statePath | ConvertFrom-Json
$lastSeededCycle = 0
if ($state.PSObject.Properties.Name -contains "last_seeded_cycle") {
    $lastSeededCycle = [int]$state.last_seeded_cycle
}

if ($lastSeededCycle -ge [int]$seedState.active_cycle) {
    [ordered]@{
        status = "already-applied"
        window = $Window
        cycle = [int]$seedState.active_cycle
        seed_package_dir = [string]$seedState.seed_package_dir
        target_repo = $TargetRepo
    } | ConvertTo-Json -Depth 8
    exit 0
}

$applyResult = & (Join-Path $PSScriptRoot "apply_patch_package.ps1") -PackageDir $seedState.seed_package_dir -TargetRepo $TargetRepo
$applyPayload = $applyResult | ConvertFrom-Json

$history = @()
if ($state.history) {
    $history = @($state.history)
}
$history += [pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    action = "cycle-seed-applied"
    item_id = ("CYCLE-SEED-{0}" -f [int]$seedState.active_cycle)
    round = 0
    package_dir = [string]$seedState.seed_package_dir
    files = @($applyPayload.applied_files)
    delete_files = @($applyPayload.deleted_files)
    source_packages = @([string]$seedState.seed_package_dir)
}

$state.history = $history
$state.last_seeded_cycle = [int]$seedState.active_cycle
$state.last_seed_package_dir = [string]$seedState.seed_package_dir
$state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8

[ordered]@{
    status = "applied"
    window = $Window
    cycle = [int]$seedState.active_cycle
    seed_package_dir = [string]$seedState.seed_package_dir
    target_repo = $TargetRepo
} | ConvertTo-Json -Depth 8
