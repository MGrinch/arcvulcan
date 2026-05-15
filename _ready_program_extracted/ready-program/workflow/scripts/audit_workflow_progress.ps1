param(
    [string]$RepoRoot
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

function Test-ManifestApplied {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageDir,
        [Parameter(Mandatory = $true)]
        [string]$TargetRepo
    )

    $manifestPath = Join-Path $PackageDir "manifest.json"
    $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json

    $missingTargets = @()
    $hashMismatches = @()
    $unexpectedDeletes = @()

    foreach ($relative in @($manifest.files)) {
        $source = Join-Path $PackageDir ("files/" + $relative)
        $target = Join-Path $TargetRepo $relative
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            $missingTargets += $relative
            continue
        }

        $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
        $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
        if ($sourceHash -ne $targetHash) {
            $hashMismatches += $relative
        }
    }

    foreach ($relative in @($manifest.delete_files)) {
        $target = Join-Path $TargetRepo $relative
        if (Test-Path -LiteralPath $target) {
            $unexpectedDeletes += $relative
        }
    }

    [pscustomobject]@{
        applied = (@($missingTargets).Count -eq 0) -and (@($hashMismatches).Count -eq 0) -and (@($unexpectedDeletes).Count -eq 0)
        missing_targets = @($missingTargets)
        hash_mismatches = @($hashMismatches)
        unexpected_delete_targets = @($unexpectedDeletes)
    }
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $workflowRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

$config = Get-Content -Raw (Join-Path $workflowRoot "config/windows.json") | ConvertFrom-Json
$workerEntries = @($config.windows | Where-Object { $_.kind -eq "worker" } | Sort-Object window)

$results = @()

foreach ($entry in $workerEntries) {
    $queuePath = Join-Path $workflowRoot $entry.queue_file
    $statePath = Join-Path $workflowRoot $entry.state_file

    $queue = Get-Content -Raw $queuePath | ConvertFrom-Json
    $state = Get-Content -Raw $statePath | ConvertFrom-Json

    $completedEntries = @($state.history | Where-Object { $_.action -eq "worker-complete" })
    $appliedBugIds = @()
    $unappliedBugIds = @()
    $historyAudit = @()

    foreach ($history in $completedEntries) {
        $packageAudit = $null
        $resolvedPackageDir = $null
        $errorMessage = $null

        try {
            $resolvedPackageDir = Resolve-WorkflowPackageDir -InputPath $history.package_dir
            $packageAudit = Test-ManifestApplied -PackageDir $resolvedPackageDir -TargetRepo $RepoRoot
        } catch {
            $errorMessage = $_.Exception.Message
            $packageAudit = [pscustomobject]@{
                applied = $false
                missing_targets = @()
                hash_mismatches = @()
                unexpected_delete_targets = @()
            }
        }

        if ($packageAudit.applied) {
            $appliedBugIds += [string]$history.item_id
        } else {
            $unappliedBugIds += [string]$history.item_id
        }

        $historyAudit += [pscustomobject]@{
            bug_id = [string]$history.item_id
            round = [int]$history.round
            package_dir = [string]$resolvedPackageDir
            applied = [bool]$packageAudit.applied
            error = $errorMessage
            missing_targets = @($packageAudit.missing_targets)
            hash_mismatches = @($packageAudit.hash_mismatches)
            unexpected_delete_targets = @($packageAudit.unexpected_delete_targets)
        }
    }

    $queuedBugIds = @($queue.items | ForEach-Object { [string]$_.bug_id })
    $staleQueued = @($queue.items | Where-Object { $appliedBugIds -contains [string]$_.bug_id })

    $results += [pscustomobject]@{
        window = [int]$entry.window
        name = [string]$entry.name
        queue_file = $queuePath
        state_file = $statePath
        queued_bug_ids = @($queuedBugIds)
        completed_applied_bug_ids = @($appliedBugIds | Sort-Object -Unique)
        completed_unapplied_bug_ids = @($unappliedBugIds | Sort-Object -Unique)
        stale_completed_items_in_queue = @($staleQueued | ForEach-Object {
                [pscustomobject]@{
                    bug_id = [string]$_.bug_id
                    queue_index = [int]$_.queue_index
                    title = [string]$_.title
                }
            })
        history_audit = @($historyAudit)
    }
}

$staleTotal = (@($results | ForEach-Object { @($_.stale_completed_items_in_queue).Count } | Measure-Object -Sum).Sum)

[ordered]@{
    audited_utc = (Get-Date).ToUniversalTime().ToString("o")
    repo_root = $RepoRoot
    workflow_root = $workflowRoot
    stale_completed_queue_items = [int]$staleTotal
    windows = @($results)
} | ConvertTo-Json -Depth 10
