param(
    [Parameter(Mandatory = $true)]
    [string]$BugId,

    [string]$ReportPath
)

$workflowRoot = Split-Path -Parent $PSScriptRoot
if (-not $ReportPath) {
    $sourceDir = Join-Path $workflowRoot "source"
    $report = Get-ChildItem -Path $sourceDir -Filter *.md | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $report) {
        throw "No report found under $sourceDir"
    }
    $ReportPath = $report.FullName
}

$text = Get-Content -Raw $ReportPath
$escaped = [regex]::Escape($BugId)
$pattern = "(?ms)^### ${escaped}:.*?(?=^### BUG-\d+:|^## |\z)"
$match = [regex]::Match($text, $pattern)
if (-not $match.Success) {
    throw "Bug section not found: $BugId"
}

$match.Value.Trim()
