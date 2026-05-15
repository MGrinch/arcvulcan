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

    [string]$PackageKind,

    [switch]$NoOp
)

function Normalize-RelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathText
    )
    $normalized = $PathText.Replace("\", "/")
    while ($normalized.StartsWith("./")) {
        $normalized = $normalized.Substring(2)
    }
    if ($normalized.StartsWith("/")) {
        $normalized = $normalized.TrimStart("/")
    }
    return $normalized
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $workflowRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

if (-not $PackageKind) {
    if ($NoOp) {
        $PackageKind = "noop"
    } else {
        $configPath = Join-Path $workflowRoot "config/windows.json"
        $config = Get-Content -Raw $configPath | ConvertFrom-Json
        $entry = $config.windows | Where-Object { $_.window -eq $Window } | Select-Object -First 1
        if (-not $entry) {
            throw "Unknown window: $Window"
        }
        if ($entry.kind -eq "precompile") {
            $PackageKind = "precompile"
        } elseif ($entry.kind -eq "final") {
            $PackageKind = "final"
        } else {
            $PackageKind = "worker"
        }
    }
}

$windowDir = Join-Path $workflowRoot ("out/window-{0:D2}" -f $Window)
$safeItemId = ($ItemId -replace "[^A-Za-z0-9._-]", "_")
$packageDir = Join-Path $windowDir ("round-{0:D2}__{1}" -f $Round, $safeItemId)
$filesDir = Join-Path $packageDir "files"

if (Test-Path $packageDir) {
    Remove-Item -Recurse -Force $packageDir
}
New-Item -ItemType Directory -Path $filesDir -Force | Out-Null

$normalizedFiles = @()
foreach ($file in @($Files)) {
    $relative = Normalize-RelativePath -PathText $file
    $source = Join-Path $RepoRoot $relative
    if (-not (Test-Path $source -PathType Leaf)) {
        throw "Cannot package missing file: $source"
    }
    $target = Join-Path $filesDir $relative
    $targetParent = Split-Path -Parent $target
    if ($targetParent) {
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
    $normalizedFiles += $relative
}

$normalizedDeletes = @()
foreach ($file in @($DeleteFiles)) {
    $normalizedDeletes += Normalize-RelativePath -PathText $file
}

$manifest = [ordered]@{
    window = $Window
    round = $Round
    item_id = $ItemId
    kind = $PackageKind
    noop = [bool]$NoOp
    created_utc = (Get-Date).ToUniversalTime().ToString("o")
    files = @($normalizedFiles)
    delete_files = @($normalizedDeletes)
    source_packages = @($SourcePackages)
}

$manifestPath = Join-Path $packageDir "manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

$applyScript = @'
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRepo
)

$packageDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifest = Get-Content -Raw (Join-Path $packageDir "manifest.json") | ConvertFrom-Json
$TargetRepo = (Resolve-Path $TargetRepo).Path

foreach ($relative in @($manifest.delete_files)) {
    $target = Join-Path $TargetRepo $relative
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
}

foreach ($relative in @($manifest.files)) {
    $source = Join-Path $packageDir ("files/" + $relative)
    $target = Join-Path $TargetRepo $relative
    $parent = Split-Path -Parent $target
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}
'@
$applyPath = Join-Path $packageDir "apply_patch.ps1"
$applyScript | Set-Content -Path $applyPath -Encoding UTF8

(Resolve-Path $packageDir).Path
