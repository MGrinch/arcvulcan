param(
    [Parameter(Mandatory = $true)]
    [string[]]$PackageDir,

    [string]$TargetRepo
)

if (-not $TargetRepo) {
    $workflowRoot = Split-Path -Parent $PSScriptRoot
    $TargetRepo = Split-Path -Parent $workflowRoot
}
$TargetRepo = (Resolve-Path $TargetRepo).Path

$copySources = @{}
$deleteSources = @{}

foreach ($dir in @($PackageDir)) {
    $resolvedDir = (Resolve-Path $dir).Path
    $manifestPath = Join-Path $resolvedDir "manifest.json"
    if (-not (Test-Path $manifestPath -PathType Leaf)) {
        throw "Missing manifest: $manifestPath"
    }
    $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json

    foreach ($relative in @($manifest.files)) {
        $source = Join-Path $resolvedDir ("files/" + $relative)
        if ($copySources.ContainsKey($relative)) {
            $existingHash = (Get-FileHash -Algorithm SHA256 $copySources[$relative]).Hash
            $newHash = (Get-FileHash -Algorithm SHA256 $source).Hash
            if ($existingHash -ne $newHash) {
                throw "Overlapping package file with different contents: $relative"
            }
        } else {
            $copySources[$relative] = $source
        }
    }

    foreach ($relative in @($manifest.delete_files)) {
        if ($copySources.ContainsKey($relative)) {
            throw "Delete/copy overlap detected for $relative"
        }
        if (-not $deleteSources.ContainsKey($relative)) {
            $deleteSources[$relative] = $resolvedDir
        }
    }
}

foreach ($relative in $deleteSources.Keys) {
    $target = Join-Path $TargetRepo $relative
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
}

foreach ($relative in $copySources.Keys) {
    $source = $copySources[$relative]
    $target = Join-Path $TargetRepo $relative
    $parent = Split-Path -Parent $target
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}

[ordered]@{
    target_repo = $TargetRepo
    package_dirs = @($PackageDir)
    applied_files = @($copySources.Keys | Sort-Object)
    deleted_files = @($deleteSources.Keys | Sort-Object)
} | ConvertTo-Json -Depth 8
