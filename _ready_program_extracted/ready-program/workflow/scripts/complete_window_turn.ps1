param(
    [Parameter(Mandatory = $true)]
    [int]$Window,

    [Parameter(Mandatory = $true)]
    [string]$ItemId,

    [Parameter(Mandatory = $true)]
    [int]$Round,

    [string]$RepoRoot,

    [string[]]$Files = @(),

    [string[]]$DeleteFiles = @(),

    [string[]]$SourcePackages = @(),

    [switch]$PublishCycleHandoff
)

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
if (-not $entry) {
    throw "Unknown window: $Window"
}

if ($PublishCycleHandoff -and $entry.kind -ne "final") {
    throw "PublishCycleHandoff is valid only for the configured final compiler window."
}

$action = if ($entry.kind -eq "worker") { "worker-complete" } else { "batch-complete" }
$expectedKind = if ($entry.kind -eq "worker") { "worker" } elseif ($entry.kind -eq "final") { "final" } else { "precompile" }

$packageDir = & (Join-Path $PSScriptRoot "new_patch_package.ps1") `
    -Window $Window `
    -ItemId $ItemId `
    -Round $Round `
    -RepoRoot $RepoRoot `
    -Files $Files `
    -DeleteFiles $DeleteFiles `
    -SourcePackages $SourcePackages

$verification = & (Join-Path $PSScriptRoot "verify_package_manifest.ps1") `
    -PackagePath $packageDir `
    -ExpectedWindow $Window `
    -ExpectedRound $Round `
    -ExpectedItemId $ItemId `
    -ExpectedKind $expectedKind `
    -ErrorOnFailure | ConvertFrom-Json

$manifest = $verification.manifest
$state = & (Join-Path $PSScriptRoot "set_window_state.ps1") `
    -Window $Window `
    -Action $action `
    -ItemId $ItemId `
    -Round $Round `
    -PackageDir $packageDir `
    -Files @($manifest.files) `
    -DeleteFiles @($manifest.delete_files) `
    -SourcePackages @($manifest.source_packages) | ConvertFrom-Json

$handoff = $null
$replyLines = @([string]$packageDir)
if ($PublishCycleHandoff) {
    $handoff = & (Join-Path $PSScriptRoot "publish_cycle_handoff.ps1") -PackagePath $packageDir | ConvertFrom-Json
    $replyLines = @(
        [string]$packageDir,
        [string]$handoff.ready_repo_dir,
        [string]$handoff.backward_sync_dir
    )
}

[ordered]@{
    completed_utc = (Get-Date).ToUniversalTime().ToString("o")
    window = $Window
    kind = $expectedKind
    item_id = $ItemId
    round = $Round
    action = $action
    package_dir = [string]$packageDir
    verification = $verification
    state = $state
    handoff = $handoff
    reply_lines = @($replyLines)
} | ConvertTo-Json -Depth 10
