param(
    [Parameter(Mandatory = $true)]
    [int]$Window,

    [switch]$CreateNoOps
)

function New-NoopPackage {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TargetWindow,
        [Parameter(Mandatory = $true)]
        [int]$Round,
        [Parameter(Mandatory = $true)]
        [int]$SourceWindow
    )
    $scriptPath = Join-Path $PSScriptRoot "new_patch_package.ps1"
    & $scriptPath -Window $TargetWindow -ItemId ("NOOP-window-{0:D2}" -f $SourceWindow) -Round $Round -PackageKind "noop" -NoOp
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}
if (($entry.kind -ne "merge") -and ($entry.kind -ne "precompile") -and ($entry.kind -ne "final")) {
    throw "Window $Window is not a precompiler or final compiler"
}

$statePath = Join-Path $workflowRoot $entry.state_file
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

$nextRound = [int]$state.completed_rounds + 1

$packages = @()
$waitingOn = @()
$hasRealPackage = $false

foreach ($upstream in @($entry.upstreams)) {
    $upstreamEntry = $config.windows | Where-Object { $_.window -eq $upstream } | Select-Object -First 1
    $upstreamState = Get-Content -Raw (Join-Path $workflowRoot $upstreamEntry.state_file) | ConvertFrom-Json
    $matchingHistory = @($upstreamState.history | Where-Object { [int]$_.round -eq $nextRound })

    if ($matchingHistory.Count -gt 0) {
        $latest = $matchingHistory[-1]
        $manifest = Get-Content -Raw (Join-Path $latest.package_dir "manifest.json") | ConvertFrom-Json
        if (-not $manifest.noop) {
            $hasRealPackage = $true
        }
        $packages += [pscustomobject]@{
            window = $upstream
            package_dir = $latest.package_dir
            noop = [bool]$manifest.noop
            files = @($manifest.files)
            delete_files = @($manifest.delete_files)
        }
        continue
    }

    $upstreamComplete = $false
    if ($upstreamEntry.kind -eq "worker") {
        $queue = Get-Content -Raw (Join-Path $workflowRoot $upstreamEntry.queue_file) | ConvertFrom-Json
        $upstreamComplete = [int]$upstreamState.completed_count -ge @($queue.items).Count
    } else {
        $upstreamComplete = $upstreamState.status -eq "complete"
    }

    if ($upstreamComplete) {
        $noopPackage = $null
        if ($CreateNoOps) {
            $noopPackage = New-NoopPackage -TargetWindow $Window -Round $nextRound -SourceWindow $upstream
        }
        $packages += [pscustomobject]@{
            window = $upstream
            package_dir = $noopPackage
            noop = $true
            files = @()
            delete_files = @()
        }
    } else {
        $waitingOn += [pscustomobject]@{
            window = $upstream
            round = $nextRound
        }
    }
}

if ($waitingOn.Count -gt 0) {
    [ordered]@{
        ready = $false
        status = "waiting"
        window = $Window
        round = $nextRound
        waiting_on = $waitingOn
        packages = $packages
    } | ConvertTo-Json -Depth 8
    exit 0
}

if (-not $hasRealPackage) {
    $state.status = "complete"
    $state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8
    [ordered]@{
        ready = $false
        status = "complete"
        window = $Window
        round = $nextRound
        packages = $packages
    } | ConvertTo-Json -Depth 8
    exit 0
}

[ordered]@{
    ready = $true
    status = "ready"
    window = $Window
    name = $entry.name
    round = $nextRound
    state_file = $statePath
    packages = $packages
} | ConvertTo-Json -Depth 8
