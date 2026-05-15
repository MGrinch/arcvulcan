param(
    [string]$WorkflowRoot,
    [string]$OutputPath,
    [switch]$ErrorOnFailure
)

function Add-Check {
    param(
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[object]]$Checks,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [bool]$Ok,
        [Parameter(Mandatory = $true)]
        [string]$Details
    )

    $Checks.Add([pscustomobject]@{
        name = $Name
        ok = $Ok
        details = $Details
    }) | Out-Null
}

function Test-FileContainsAll {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string[]]$Needles
    )

    $content = Get-Content -Raw $Path
    $missing = @()
    foreach ($needle in $Needles) {
        if ($content -notlike ("*" + $needle + "*")) {
            $missing += $needle
        }
    }
    return [pscustomobject]@{
        ok = ($missing.Count -eq 0)
        missing = @($missing)
    }
}

if (-not $WorkflowRoot) {
    $WorkflowRoot = Split-Path -Parent $PSScriptRoot
}
$WorkflowRoot = (Resolve-Path $WorkflowRoot).Path

$checks = New-Object 'System.Collections.Generic.List[object]'
$requiredWorkflowFiles = @(
    "STATUS.md",
    "BACKLOG_STATUS.json",
    "config/windows.json",
    "START_HERE.md",
    "AGENTS.md",
    "WINDOW_SYSTEM_PROMPTS.md",
    "CYCLE_ORCHESTRA_PROMPTS.md",
    "UNRESOLVED_EXECUTION_INTELLIGENCE.md",
    "shared/operating-rules.md",
    "shared/package-format.md",
    "shared/cycle-reset.md",
    "shared/merge-rules.md",
    "roles/worker.md",
    "roles/precompiler.md",
    "roles/final-compiler.md",
    "scripts/start_window_turn.ps1",
    "scripts/complete_window_turn.ps1",
    "scripts/publish_cycle_handoff.ps1",
    "scripts/verify_package_manifest.ps1",
    "scripts/build_window_system_prompts.ps1",
    "scripts/validate_workflow_grounding.ps1",
    "scripts/repartition_workflow_topology.ps1"
)

$missingFiles = @()
foreach ($relativePath in $requiredWorkflowFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $WorkflowRoot $relativePath))) {
        $missingFiles += $relativePath
    }
}
Add-Check -Checks $checks -Name "required-files" -Ok ($missingFiles.Count -eq 0) -Details $(if ($missingFiles.Count -eq 0) { "All required workflow files are present." } else { "Missing: " + ($missingFiles -join ", ") })

$rootFolder = Split-Path -Parent $WorkflowRoot
$rootFiles = @(
    "00_WINDOW_FARM_START_HERE.md",
    "WINDOW_ROLE_ENTRYPOINT.txt",
    "README.md"
)
$missingRootFiles = @()
foreach ($relativePath in $rootFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $rootFolder $relativePath))) {
        $missingRootFiles += $relativePath
    }
}
Add-Check -Checks $checks -Name "required-root-files" -Ok ($missingRootFiles.Count -eq 0) -Details $(if ($missingRootFiles.Count -eq 0) { "All required root grounding files are present." } else { "Missing: " + ($missingRootFiles -join ", ") })

$configPath = Join-Path $WorkflowRoot "config/windows.json"
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$windows = @($config.windows)
$workerEntries = @($windows | Where-Object { $_.kind -eq "worker" })
$workerCount = @($windows | Where-Object { $_.kind -eq "worker" }).Count
$precompileCount = @($windows | Where-Object { $_.kind -eq "precompile" }).Count
$finalCount = @($windows | Where-Object { $_.kind -eq "final" }).Count
$configOk = ($windows.Count -eq 18) -and ($workerCount -eq 15) -and ($precompileCount -eq 2) -and ($finalCount -eq 1)
Add-Check -Checks $checks -Name "window-config-shape" -Ok $configOk -Details "windows=$($windows.Count); workers=$workerCount; precompilers=$precompileCount; finals=$finalCount"

$referenceErrors = @()
foreach ($entry in $windows) {
    foreach ($field in @("role_file", "state_file")) {
        if ($entry.PSObject.Properties.Name -contains $field) {
            $path = Join-Path $WorkflowRoot $entry.$field
            if (-not (Test-Path -LiteralPath $path)) {
                $referenceErrors += "window $($entry.window) missing $field -> $($entry.$field)"
            }
        }
    }
    if (($entry.kind -eq "worker") -and ($entry.PSObject.Properties.Name -contains "queue_file")) {
        $path = Join-Path $WorkflowRoot $entry.queue_file
        if (-not (Test-Path -LiteralPath $path)) {
            $referenceErrors += "window $($entry.window) missing queue_file -> $($entry.queue_file)"
        }
    }
}
Add-Check -Checks $checks -Name "window-file-references" -Ok ($referenceErrors.Count -eq 0) -Details $(if ($referenceErrors.Count -eq 0) { "All configured role/state/queue files exist." } else { $referenceErrors -join "; " })

$expectedQueueFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($entry in $workerEntries) {
    $null = $expectedQueueFiles.Add((Join-Path $WorkflowRoot $entry.queue_file))
}
$actualQueueFiles = @(Get-ChildItem -LiteralPath (Join-Path $WorkflowRoot "queues") -Filter "window-*.json" -File | ForEach-Object { $_.FullName })
$unexpectedQueueFiles = @($actualQueueFiles | Where-Object { -not $expectedQueueFiles.Contains($_) })
Add-Check -Checks $checks -Name "queue-file-topology" -Ok ($unexpectedQueueFiles.Count -eq 0) -Details $(if ($unexpectedQueueFiles.Count -eq 0) { "No stale worker queue files remain outside the configured worker topology." } else { "Unexpected queue files: " + ($unexpectedQueueFiles -join ", ") })

$cycleSeedPath = Join-Path $WorkflowRoot "state/cycle-seed.json"
$cycleSeed = Get-Content -Raw $cycleSeedPath | ConvertFrom-Json
$requiredSeedFields = @(
    "active_cycle",
    "seed_package_dir",
    "seed_source_window",
    "seed_round",
    "seed_kind",
    "seed_prepared_utc",
    "seed_source_final_package_dir",
    "seed_backward_sync_dir",
    "seed_backward_sync_zip",
    "seed_ready_repo_dir",
    "seed_ready_repo_zip"
)
$missingSeedFields = @()
foreach ($field in $requiredSeedFields) {
    if ($cycleSeed.PSObject.Properties.Name -notcontains $field) {
        $missingSeedFields += $field
    }
}
Add-Check -Checks $checks -Name "cycle-seed-shape" -Ok ($missingSeedFields.Count -eq 0) -Details $(if ($missingSeedFields.Count -eq 0) { "cycle-seed.json contains the required fields." } else { "Missing: " + ($missingSeedFields -join ", ") })

$startHereCheck = Test-FileContainsAll -Path (Join-Path $WorkflowRoot "START_HERE.md") -Needles @("start_window_turn.ps1", "complete_window_turn.ps1", "publish_cycle_handoff.ps1", "verify_package_manifest.ps1", "backward-sync patch")
Add-Check -Checks $checks -Name "workflow-start-here-content" -Ok $startHereCheck.ok -Details $(if ($startHereCheck.ok) { "workflow/START_HERE.md contains the canonical cycle and verification rules." } else { "Missing: " + ($startHereCheck.missing -join ", ") })

$rootStartCheck = Test-FileContainsAll -Path (Join-Path $rootFolder "00_WINDOW_FARM_START_HERE.md") -Needles @("workflow/STATUS.md", "workflow/WINDOW_SYSTEM_PROMPTS.md", "ready-program artifact", "backward-sync patch")
Add-Check -Checks $checks -Name "root-start-content" -Ok $rootStartCheck.ok -Details $(if ($rootStartCheck.ok) { "Root operator entrypoint references the canonical workflow files and handoff artifacts." } else { "Missing: " + ($rootStartCheck.missing -join ", ") })

$operatingRulesCheck = Test-FileContainsAll -Path (Join-Path $WorkflowRoot "shared/operating-rules.md") -Needles @("start_window_turn.ps1", "complete_window_turn.ps1", "validate_workflow_grounding.ps1", "verify_package_manifest.ps1", "publish_cycle_handoff.ps1")
Add-Check -Checks $checks -Name "operating-rules-content" -Ok $operatingRulesCheck.ok -Details $(if ($operatingRulesCheck.ok) { "Operating rules include package verification and cycle-close validation." } else { "Missing: " + ($operatingRulesCheck.missing -join ", ") })

$orchestraCheck = Test-FileContainsAll -Path (Join-Path $WorkflowRoot "CYCLE_ORCHESTRA_PROMPTS.md") -Needles @("sync-only", "ready-program artifact", "backward-sync patch")
Add-Check -Checks $checks -Name "orchestra-content" -Ok $orchestraCheck.ok -Details $(if ($orchestraCheck.ok) { "Cycle orchestra sheet includes sync and cycle-close guidance." } else { "Missing: " + ($orchestraCheck.missing -join ", ") })

$tempPromptPath = Join-Path $env:TEMP ("window_prompts_" + [guid]::NewGuid().ToString("N") + ".md")
$null = & (Join-Path $WorkflowRoot "scripts/build_window_system_prompts.ps1") -WorkflowRoot $WorkflowRoot -OutPath $tempPromptPath | ConvertFrom-Json
$currentPromptContent = Get-Content -Raw (Join-Path $WorkflowRoot "WINDOW_SYSTEM_PROMPTS.md")
$builtPromptContent = Get-Content -Raw $tempPromptPath
Remove-Item -LiteralPath $tempPromptPath -Force
Add-Check -Checks $checks -Name "window-system-prompts-current" -Ok ($currentPromptContent -eq $builtPromptContent) -Details $(if ($currentPromptContent -eq $builtPromptContent) { "WINDOW_SYSTEM_PROMPTS.md matches the generated canonical prompt pack." } else { "WINDOW_SYSTEM_PROMPTS.md has drifted from the generated canonical prompt pack." })

$failedChecks = @($checks | Where-Object { -not $_.ok })
$payload = [pscustomobject]@{
    checked_utc = (Get-Date).ToUniversalTime().ToString("o")
    workflow_root = $WorkflowRoot
    ok = ($failedChecks.Count -eq 0)
    check_count = $checks.Count
    failed_count = $failedChecks.Count
    checks = @($checks.ToArray())
}

if ($OutputPath) {
    $outputDir = Split-Path -Parent $OutputPath
    if ($outputDir) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -Path $OutputPath -Encoding UTF8
}

if ($ErrorOnFailure -and $failedChecks.Count -gt 0) {
    $message = "Workflow grounding validation failed:`n- " + (($failedChecks | ForEach-Object { $_.name + ": " + $_.details }) -join "`n- ")
    throw $message
}

$payload | ConvertTo-Json -Depth 8
