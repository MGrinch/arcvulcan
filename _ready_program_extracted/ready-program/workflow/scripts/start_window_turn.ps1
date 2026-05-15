param(
    [Parameter(Mandatory = $true)]
    [int]$Window,

    [switch]$AutoApplySeed,

    [switch]$SyncOnly,

    [switch]$CreateNoOps
)

function Get-AbsoluteWorkflowPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot,
        [string]$RelativePath
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return $null
    }
    return (Join-Path $WorkflowRoot $RelativePath)
}

function Get-SelectorPayload {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Entry
    )

    if ($Entry.kind -eq "worker") {
        return (& (Join-Path $PSScriptRoot "get_next_worker_item.ps1") -Window $Window | ConvertFrom-Json)
    }

    return (& (Join-Path $PSScriptRoot "get_next_merge_batch.ps1") -Window $Window -CreateNoOps:$CreateNoOps | ConvertFrom-Json)
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $workflowRoot "config/windows.json"
$statusPath = Join-Path $workflowRoot "STATUS.md"
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}

$rolePath = Get-AbsoluteWorkflowPath -WorkflowRoot $workflowRoot -RelativePath $entry.role_file
$statePath = Get-AbsoluteWorkflowPath -WorkflowRoot $workflowRoot -RelativePath $entry.state_file
$queuePath = Get-AbsoluteWorkflowPath -WorkflowRoot $workflowRoot -RelativePath $entry.queue_file
$sharedPaths = @(
    (Join-Path $workflowRoot "shared/operating-rules.md"),
    (Join-Path $workflowRoot "shared/package-format.md"),
    (Join-Path $workflowRoot "shared/cycle-reset.md")
)
if ($entry.kind -ne "worker") {
    $sharedPaths += (Join-Path $workflowRoot "shared/merge-rules.md")
}

$initialSelector = Get-SelectorPayload -Entry $entry
$selector = $initialSelector
$seedResult = $null
$seedApplied = $false

if ($AutoApplySeed -and ($selector.status -eq "seed-required")) {
    $seedResult = & (Join-Path $PSScriptRoot "apply_cycle_seed.ps1") -Window $Window | ConvertFrom-Json
    $seedApplied = ($seedResult.status -eq "applied")
    $selector = Get-SelectorPayload -Entry $entry
}

$syncPath = $statePath
if ($seedResult -and $seedResult.PSObject.Properties.Name -contains "seed_package_dir" -and $seedResult.seed_package_dir) {
    $syncPath = [string]$seedResult.seed_package_dir
} elseif ($selector.PSObject.Properties.Name -contains "seed_package_dir" -and $selector.seed_package_dir) {
    $syncPath = [string]$selector.seed_package_dir
}

$replyContract = if ($entry.kind -eq "final") {
    "three-line-final-paths"
} elseif ($entry.kind -eq "worker") {
    "single-package-path"
} else {
    "single-package-path"
}

$payload = [ordered]@{
    started_utc = (Get-Date).ToUniversalTime().ToString("o")
    window = [int]$entry.window
    kind = [string]$entry.kind
    name = [string]$entry.name
    area = [string]$entry.area
    sync_only = [bool]$SyncOnly
    auto_apply_seed = [bool]$AutoApplySeed
    seed_applied = [bool]$seedApplied
    seed_result = $seedResult
    selector_status = [string]$selector.status
    ready = [bool]$selector.ready
    status_file = $statusPath
    config_file = $configPath
    role_file = $rolePath
    state_file = $statePath
    queue_file = $queuePath
    shared_files = @($sharedPaths)
    reply_contract = $replyContract
    sync_path = $syncPath
    selector = $selector
}

if ($entry.kind -eq "worker" -and $selector.status -eq "ready") {
    $payload["report_file"] = [string]$selector.report_file
    $payload["item_id"] = [string]$selector.item.bug_id
    $payload["round"] = [int]$selector.round
    $payload["title"] = [string]$selector.item.title
}

if ($entry.kind -ne "worker" -and ($selector.PSObject.Properties.Name -contains "round")) {
    $payload["round"] = [int]$selector.round
}

if ($selector.status -eq "waiting" -and $selector.waiting_on) {
    $firstWait = @($selector.waiting_on)[0]
    $firstPackage = @($selector.packages | Where-Object { $_.package_dir }) | Select-Object -First 1
    $relevantPath = if ($firstPackage) { [string]$firstPackage.package_dir } else { $statePath }
    $payload["suggested_reply"] = "WAITING ON WINDOW {0:D2} ROUND {1} {2}" -f [int]$firstWait.window, [int]$firstWait.round, $relevantPath
}

if ($selector.status -eq "complete") {
    $payload["suggested_reply"] = "WINDOW {0:D2} COMPLETE" -f [int]$entry.window
}

if ($SyncOnly) {
    $roundOrCycle = if ($selector.PSObject.Properties.Name -contains "cycle" -and $selector.cycle) {
        "cycle-{0}" -f [int]$selector.cycle
    } elseif ($selector.PSObject.Properties.Name -contains "round" -and $selector.round) {
        "round-{0}" -f [int]$selector.round
    } else {
        "state"
    }
    $payload["suggested_sync_reply"] = "WINDOW {0:D2} SYNCED {1} {2} {3}" -f [int]$entry.window, [string]$selector.status, $roundOrCycle, $syncPath
}

$payload | ConvertTo-Json -Depth 10
