param(
    [string]$PackagePath,
    [string]$RepoRoot,
    [switch]$Force
)

function Resolve-WorkflowPackageDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath
    )

    $resolved = (Resolve-Path $InputPath).Path
    $manifestPath = Join-Path $resolved "manifest.json"
    if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
        return $resolved
    }

    $manifest = Get-ChildItem -LiteralPath $resolved -Recurse -Filter manifest.json | Sort-Object FullName | Select-Object -First 1
    if (-not $manifest) {
        throw "Could not locate manifest.json under package path: $resolved"
    }
    return (Split-Path -Parent $manifest.FullName)
}

function Get-NextCycleNumber {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot
    )

    $seedPath = Join-Path $WorkflowRoot "state/cycle-seed.json"
    if (-not (Test-Path -LiteralPath $seedPath)) {
        return 1
    }

    $seedState = Get-Content -Raw $seedPath | ConvertFrom-Json
    return ([int]$seedState.active_cycle + 1)
}

function Test-ExcludedRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $normalized = $RelativePath.Replace("\", "/").TrimStart("./")
    if ($normalized -eq ".git") { return $true }
    if ($normalized -eq ".pytest_cache") { return $true }
    if ($normalized -like "workflow/handoffs*") { return $true }
    if ($normalized -like "workflow/cache/cycle-seed*") { return $true }
    if ($normalized -like "*/__pycache__*") { return $true }
    if ($normalized -eq "__pycache__") { return $true }
    return $false
}

function Copy-RepoSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,
        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $DestinationRoot)) {
        New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    }

    $prefixLength = $SourceRoot.Length
    Get-ChildItem -LiteralPath $SourceRoot -Force | ForEach-Object {
        $stack = @($_)
        while ($stack.Count -gt 0) {
            $current = $stack[0]
            if ($stack.Count -eq 1) {
                $stack = @()
            } else {
                $stack = @($stack[1..($stack.Count - 1)])
            }

            $relative = $current.FullName.Substring($prefixLength).TrimStart("\")
            if ([string]::IsNullOrWhiteSpace($relative)) {
                continue
            }
            if (Test-ExcludedRelativePath -RelativePath $relative) {
                continue
            }

            $target = Join-Path $DestinationRoot $relative
            if ($current.PSIsContainer) {
                New-Item -ItemType Directory -Path $target -Force | Out-Null
                $children = @(Get-ChildItem -LiteralPath $current.FullName -Force)
                if ($children.Count -gt 0) {
                    $stack = @($children) + $stack
                }
                continue
            }

            $parent = Split-Path -Parent $target
            if ($parent) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $current.FullName -Destination $target -Force
        }
    }
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$finalEntry = $config.windows | Where-Object { $_.kind -eq "final" } | Select-Object -First 1
if (-not $finalEntry) {
    throw "Could not locate the final compiler window in workflow/config/windows.json."
}
$finalWindow = [int]$finalEntry.window
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $workflowRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

if (-not $PackagePath) {
    $finalOut = Join-Path $workflowRoot $finalEntry.output_root
    $latest = Get-ChildItem -LiteralPath $finalOut -Directory | Sort-Object Name | Select-Object -Last 1
    if (-not $latest) {
        throw "No final package was found under $finalOut."
    }
    $PackagePath = $latest.FullName
}

$finalPackageDir = Resolve-WorkflowPackageDir -InputPath $PackagePath
$finalManifest = Get-Content -Raw (Join-Path $finalPackageDir "manifest.json") | ConvertFrom-Json
if ([int]$finalManifest.window -ne $finalWindow) {
    throw "publish_cycle_handoff.ps1 expects a package from final window $finalWindow."
}
if ([string]$finalManifest.kind -ne "final") {
    throw "publish_cycle_handoff.ps1 expects a final package, found kind '$($finalManifest.kind)'."
}
$null = & (Join-Path $PSScriptRoot "verify_package_manifest.ps1") `
    -PackagePath $finalPackageDir `
    -ExpectedWindow $finalWindow `
    -ExpectedRound ([int]$finalManifest.round) `
    -ExpectedKind final `
    -ErrorOnFailure | ConvertFrom-Json

$nextCycle = Get-NextCycleNumber -WorkflowRoot $workflowRoot
$handoffRoot = Join-Path $workflowRoot ("handoffs/cycle-{0:D2}" -f $nextCycle)
if (Test-Path -LiteralPath $handoffRoot) {
    if (-not $Force) {
        throw "Handoff output already exists: $handoffRoot"
    }
    Remove-Item -Recurse -Force $handoffRoot
}
New-Item -ItemType Directory -Path $handoffRoot -Force | Out-Null

$backwardSyncDir = Join-Path $handoffRoot "backward-sync-patch"
Copy-Item -LiteralPath $finalPackageDir -Destination $backwardSyncDir -Recurse -Force

$backwardSyncZip = Join-Path $handoffRoot ("cycle-{0:D2}_backward-sync.zip" -f $nextCycle)
if (Test-Path -LiteralPath $backwardSyncZip) {
    Remove-Item -Force $backwardSyncZip
}
Compress-Archive -LiteralPath $backwardSyncDir -DestinationPath $backwardSyncZip -Force

$readyRepoParent = Join-Path $handoffRoot "ready-program"
$readyRepoDir = Join-Path $readyRepoParent (Split-Path -Leaf $RepoRoot)

$readyRepoZip = Join-Path $handoffRoot ("{0}_cycle-{1:D2}_ready.zip" -f (Split-Path -Leaf $RepoRoot), $nextCycle)
if (Test-Path -LiteralPath $readyRepoZip) {
    Remove-Item -Force $readyRepoZip
}

$handoffReadmePath = Join-Path $handoffRoot "HANDOFF_README.md"
$handoffReadme = @"
# Cycle $("{0:D2}" -f $nextCycle) Handoff

This handoff was published by window $finalWindow after a successful final merge.

Artifacts:

- `backward-sync-patch/`: apply this patch to lagging windows through the normal cycle-seed flow
- `cycle-$("{0:D2}" -f $nextCycle)_backward-sync.zip`: zipped copy of the backward-sync patch
- `ready-program/`: open this grounded repo snapshot in fresh windows
- `$(Split-Path -Leaf $readyRepoZip)`: zipped copy of the ready-program snapshot
- `workflow-validation.json`: proof that the workflow grounding passed validation after cycle close

Rules:

1. Fresh windows should use the ready-program artifact.
2. Lagging windows `01` through `17` should apply the backward-sync patch before the next compute step.
3. Window `18` does not need a sync-only pass after it publishes the handoff.
4. Do not manually revive removed queue items or repost stale repo copies after this handoff.
"@
Set-Content -Path $handoffReadmePath -Value $handoffReadme -Encoding UTF8

$null = & (Join-Path $PSScriptRoot "rebase_unresolved_backlog.ps1") | ConvertFrom-Json
$null = & (Join-Path $PSScriptRoot "refresh_workflow_status.ps1") | ConvertFrom-Json
$null = & (Join-Path $PSScriptRoot "build_window_system_prompts.ps1") -WorkflowRoot $workflowRoot | ConvertFrom-Json

$setSeedPayload = & (Join-Path $PSScriptRoot "set_cycle_seed.ps1") `
    -PackagePath $backwardSyncDir `
    -Cycle $nextCycle `
    -Force `
    -SourceFinalPackageDir $finalPackageDir `
    -BackwardSyncDir $backwardSyncDir `
    -BackwardSyncZip $backwardSyncZip `
    -ReadyRepoDir $readyRepoDir `
    -ReadyRepoZip $readyRepoZip
$null = $setSeedPayload | ConvertFrom-Json

$validationReportPath = Join-Path $handoffRoot "workflow-validation.json"
$null = & (Join-Path $PSScriptRoot "validate_workflow_grounding.ps1") `
    -WorkflowRoot $workflowRoot `
    -OutputPath $validationReportPath `
    -ErrorOnFailure | ConvertFrom-Json

Copy-RepoSnapshot -SourceRoot $RepoRoot -DestinationRoot $readyRepoDir
Compress-Archive -LiteralPath $readyRepoDir -DestinationPath $readyRepoZip -Force

$null = & (Join-Path $PSScriptRoot "set_cycle_seed.ps1") `
    -PackagePath $backwardSyncDir `
    -Cycle $nextCycle `
    -Force `
    -SourceFinalPackageDir $finalPackageDir `
    -BackwardSyncDir $backwardSyncDir `
    -BackwardSyncZip $backwardSyncZip `
    -ReadyRepoDir $readyRepoDir `
    -ReadyRepoZip $readyRepoZip | ConvertFrom-Json

$handoffManifestPath = Join-Path $handoffRoot "handoff-manifest.json"
[ordered]@{
    published_utc = (Get-Date).ToUniversalTime().ToString("o")
    cycle = $nextCycle
    source_final_package_dir = $finalPackageDir
    backward_sync_dir = $backwardSyncDir
    backward_sync_zip = $backwardSyncZip
    ready_repo_dir = $readyRepoDir
    ready_repo_zip = $readyRepoZip
    handoff_readme = $handoffReadmePath
    workflow_validation_report = $validationReportPath
} | ConvertTo-Json -Depth 8 | Set-Content -Path $handoffManifestPath -Encoding UTF8

[ordered]@{
    published_utc = (Get-Date).ToUniversalTime().ToString("o")
    cycle = $nextCycle
    source_final_package_dir = $finalPackageDir
    backward_sync_dir = $backwardSyncDir
    backward_sync_zip = $backwardSyncZip
    ready_repo_dir = $readyRepoDir
    ready_repo_zip = $readyRepoZip
    handoff_readme = $handoffReadmePath
    handoff_manifest = $handoffManifestPath
    workflow_validation_report = $validationReportPath
} | ConvertTo-Json -Depth 8
