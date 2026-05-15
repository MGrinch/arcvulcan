param(
    [string]$RepoRoot,
    [string]$OutputParent
)

function Copy-RepoTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,
        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    $excludeDirs = @(
        ".git",
        ".pytest_cache",
        "__pycache__",
        "workflow\\handoffs",
        "workflow\\cache\\cycle-seed"
    )

    $roboArgs = @(
        $SourceRoot,
        $DestinationRoot,
        "/E",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD"
    ) + $excludeDirs

    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $workflowRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

if (-not $OutputParent) {
    $OutputParent = Split-Path -Parent $RepoRoot
}
$OutputParent = (Resolve-Path $OutputParent).Path

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destination = Join-Path $OutputParent ("DAEDALUS_v221_WORKFLOW_REALIGNED_READY_" + $stamp)
$zipPath = $destination + ".zip"

Copy-RepoTree -SourceRoot $RepoRoot -DestinationRoot $destination

$destinationWorkflowRoot = Join-Path $destination "workflow"
$destinationValidateScript = Join-Path $destinationWorkflowRoot "scripts/validate_workflow_grounding.ps1"
$destinationValidationReport = Join-Path $destinationWorkflowRoot "WORKFLOW_VALIDATION_REPORT.json"
if (Test-Path -LiteralPath $destinationValidateScript) {
    $null = & $destinationValidateScript -WorkflowRoot $destinationWorkflowRoot -OutputPath $destinationValidationReport -ErrorOnFailure | ConvertFrom-Json
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -LiteralPath $destination -DestinationPath $zipPath -Force

$summaryPath = Join-Path $destination "WORKFLOW_REALIGNMENT_SUMMARY.md"
$statusPath = Join-Path $destination "workflow/STATUS.md"
$promptsPath = Join-Path $destination "workflow/CYCLE_ORCHESTRA_PROMPTS.md"
$handoffScriptPath = Join-Path $destination "workflow/scripts/publish_cycle_handoff.ps1"

[ordered]@{
    created_utc = (Get-Date).ToUniversalTime().ToString("o")
    folder = $destination
    zip = $zipPath
    summary_exists = (Test-Path -LiteralPath $summaryPath)
    status_exists = (Test-Path -LiteralPath $statusPath)
    prompts_exists = (Test-Path -LiteralPath $promptsPath)
    handoff_script_exists = (Test-Path -LiteralPath $handoffScriptPath)
} | ConvertTo-Json -Depth 8
