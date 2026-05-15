param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,

    [int]$ExpectedWindow,

    [int]$ExpectedRound,

    [string]$ExpectedItemId,

    [ValidateSet("worker", "precompile", "final", "noop")]
    [string]$ExpectedKind,

    [switch]$ErrorOnFailure
)

function Resolve-PackageDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$WorkflowRoot
    )

    $resolved = (Resolve-Path $InputPath).Path
    if (Test-Path -LiteralPath $resolved -PathType Container) {
        return $resolved
    }

    if ([System.IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne ".zip") {
        throw "Package path must be a package directory or zip file: $resolved"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $cacheRoot = Join-Path $WorkflowRoot "cache/manifest-verify"
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    $extractRoot = Join-Path $cacheRoot ("verify_" + [guid]::NewGuid().ToString("N"))
    [System.IO.Compression.ZipFile]::ExtractToDirectory($resolved, $extractRoot)
    $manifest = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter manifest.json | Select-Object -First 1
    if (-not $manifest) {
        throw "Zip file did not contain manifest.json: $resolved"
    }
    return (Split-Path -Parent $manifest.FullName)
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$packageDir = Resolve-PackageDirectory -InputPath $PackagePath -WorkflowRoot $workflowRoot
$manifestPath = Join-Path $packageDir "manifest.json"
$applyScriptPath = Join-Path $packageDir "apply_patch.ps1"
$filesRoot = Join-Path $packageDir "files"
$errors = @()
$missingFiles = @()

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    $errors += "Missing manifest.json in package: $packageDir"
} else {
    $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
}

if (-not (Test-Path -LiteralPath $applyScriptPath -PathType Leaf)) {
    $errors += "Missing apply_patch.ps1 in package: $packageDir"
}

if (-not $errors.Count -and $manifest) {
    if ($PSBoundParameters.ContainsKey("ExpectedWindow") -and ([int]$manifest.window -ne $ExpectedWindow)) {
        $errors += "Expected window $ExpectedWindow but found $([int]$manifest.window)."
    }
    if ($PSBoundParameters.ContainsKey("ExpectedRound") -and ([int]$manifest.round -ne $ExpectedRound)) {
        $errors += "Expected round $ExpectedRound but found $([int]$manifest.round)."
    }
    if ($PSBoundParameters.ContainsKey("ExpectedItemId") -and ([string]$manifest.item_id -ne $ExpectedItemId)) {
        $errors += "Expected item id '$ExpectedItemId' but found '$([string]$manifest.item_id)'."
    }
    if ($PSBoundParameters.ContainsKey("ExpectedKind") -and ([string]$manifest.kind -ne $ExpectedKind)) {
        $errors += "Expected kind '$ExpectedKind' but found '$([string]$manifest.kind)'."
    }

    $manifestFiles = @()
    if ($manifest.files) {
        $manifestFiles = @($manifest.files)
    }

    if (($manifest.kind -ne "noop") -and ($manifestFiles.Count -eq 0)) {
        $errors += "Non-noop package declared no files."
    }

    foreach ($relativePath in $manifestFiles) {
        $packagedPath = Join-Path $filesRoot $relativePath
        if (-not (Test-Path -LiteralPath $packagedPath)) {
            $missingFiles += [string]$relativePath
        }
    }

    if ($missingFiles.Count -gt 0) {
        $errors += "Manifest referenced missing packaged files."
    }
}

$payload = [ordered]@{
    checked_utc = (Get-Date).ToUniversalTime().ToString("o")
    ok = ($errors.Count -eq 0)
    package_dir = $packageDir
    manifest_path = $manifestPath
    apply_patch_path = $applyScriptPath
    manifest = if ($manifest) {
        [ordered]@{
            window = [int]$manifest.window
            round = [int]$manifest.round
            item_id = [string]$manifest.item_id
            kind = [string]$manifest.kind
            noop = [bool]$manifest.noop
            files = @($manifest.files)
            delete_files = @($manifest.delete_files)
            source_packages = @($manifest.source_packages)
            created_utc = [string]$manifest.created_utc
        }
    } else {
        $null
    }
    missing_files = @($missingFiles)
    errors = @($errors)
}

if ($ErrorOnFailure -and $errors.Count -gt 0) {
    $message = "Package manifest verification failed for $packageDir`n- " + ($errors -join "`n- ")
    throw $message
}

$payload | ConvertTo-Json -Depth 8
