param(
    [string]$PackagePath,

    [int]$Cycle,

    [switch]$Force,

    [string]$SourceFinalPackageDir,

    [string]$BackwardSyncDir,

    [string]$BackwardSyncZip,

    [string]$ReadyRepoDir,

    [string]$ReadyRepoZip
)

function Get-SeedStatePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot
    )
    Join-Path $WorkflowRoot "state/cycle-seed.json"
}

function Resolve-StorablePath {
    param(
        [string]$PathValue
    )

    if (-not $PathValue) {
        return $null
    }

    if (Test-Path -LiteralPath $PathValue) {
        return (Resolve-Path $PathValue).Path
    }

    return [System.IO.Path]::GetFullPath($PathValue)
}

function Read-SeedState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StatePath
    )
    if (Test-Path -LiteralPath $StatePath) {
        return Get-Content -Raw $StatePath | ConvertFrom-Json
    }
    return [pscustomobject]@{
        active_cycle = 1
        seed_package_dir = $null
        seed_source_window = $null
        seed_round = $null
        seed_kind = $null
        seed_prepared_utc = $null
        seed_source_final_package_dir = $null
        seed_backward_sync_dir = $null
        seed_backward_sync_zip = $null
        seed_ready_repo_dir = $null
        seed_ready_repo_zip = $null
    }
}

function Resolve-PackageDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot,

        [Parameter(Mandatory = $false)]
        [string]$InputPath
    )

    $config = Get-Content -Raw (Join-Path $WorkflowRoot "config/windows.json") | ConvertFrom-Json
    if (-not $InputPath) {
        $finalEntry = $config.windows | Where-Object { $_.kind -eq "final" } | Select-Object -First 1
        if (-not $finalEntry) {
            throw "Could not locate the final compiler window."
        }
        $outputRoot = Join-Path $WorkflowRoot $finalEntry.output_root
        $latest = Get-ChildItem -LiteralPath $outputRoot -Directory | Sort-Object Name | Select-Object -Last 1
        if (-not $latest) {
            throw "No final package was found under $outputRoot."
        }
        return $latest.FullName
    }

    $resolved = (Resolve-Path $InputPath).Path
    if (Test-Path -LiteralPath $resolved -PathType Container) {
        return $resolved
    }

    if ([System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne ".zip") {
        throw "Cycle seed must be a package directory or a zip that contains a workflow package."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $cacheRoot = Join-Path $WorkflowRoot "cache/cycle-seed"
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $extractRoot = Join-Path $cacheRoot ("seed_" + $stamp)
    [System.IO.Compression.ZipFile]::ExtractToDirectory($resolved, $extractRoot)
    $manifest = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter manifest.json | Select-Object -First 1
    if (-not $manifest) {
        throw "Zip did not contain a workflow package manifest."
    }
    return (Split-Path -Parent $manifest.FullName)
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$seedStatePath = Get-SeedStatePath -WorkflowRoot $workflowRoot
$current = Read-SeedState -StatePath $seedStatePath
$resolvedPackageDir = Resolve-PackageDirectory -WorkflowRoot $workflowRoot -InputPath $PackagePath
$manifestPath = Join-Path $resolvedPackageDir "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing manifest.json in cycle seed package: $resolvedPackageDir"
}

$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
if ([bool]$manifest.noop) {
    throw "A no-op package cannot be promoted as a cycle seed."
}

$nextCycle = $Cycle
if (-not $PSBoundParameters.ContainsKey("Cycle")) {
    $nextCycle = [int]$current.active_cycle + 1
}

if ((-not $Force) -and $current.seed_package_dir -and ([int]$current.active_cycle -eq $nextCycle) -and ($current.seed_package_dir -eq $resolvedPackageDir)) {
    [ordered]@{
        status = "unchanged"
        active_cycle = [int]$current.active_cycle
        seed_package_dir = [string]$current.seed_package_dir
    } | ConvertTo-Json -Depth 8
    exit 0
}

$payload = [ordered]@{
    active_cycle = [int]$nextCycle
    seed_package_dir = $resolvedPackageDir
    seed_source_window = [int]$manifest.window
    seed_round = [int]$manifest.round
    seed_kind = [string]$manifest.kind
    seed_prepared_utc = (Get-Date).ToUniversalTime().ToString("o")
    seed_source_final_package_dir = (Resolve-StorablePath -PathValue $SourceFinalPackageDir)
    seed_backward_sync_dir = (Resolve-StorablePath -PathValue $BackwardSyncDir)
    seed_backward_sync_zip = (Resolve-StorablePath -PathValue $BackwardSyncZip)
    seed_ready_repo_dir = (Resolve-StorablePath -PathValue $ReadyRepoDir)
    seed_ready_repo_zip = (Resolve-StorablePath -PathValue $ReadyRepoZip)
}

$payload | ConvertTo-Json -Depth 8 | Set-Content -Path $seedStatePath -Encoding UTF8
$payload | ConvertTo-Json -Depth 8
