param()

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        $Payload
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Payload | ConvertTo-Json -Depth 14 | Set-Content -Path $Path -Encoding UTF8
}

function Write-TextFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value ($Content.TrimEnd() + "`r`n") -Encoding UTF8
}

function Read-JsonFileIfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return (Get-Content -Raw $Path | ConvertFrom-Json)
}

function Set-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Object,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        $Value
    )

    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        Add-Member -InputObject $Object -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function New-WindowEntry {
    param(
        [int]$Window,
        [string]$Kind,
        [string]$Name,
        [string]$Area,
        [int[]]$Upstreams = @()
    )

    $entry = [ordered]@{
        window = $Window
        kind = $Kind
        name = $Name
        area = $Area
        role_file = if ($Kind -eq "worker") { "roles/worker.md" } elseif ($Kind -eq "final") { "roles/final-compiler.md" } else { "roles/precompiler.md" }
        state_file = ("state/window-{0:D2}.json" -f $Window)
        output_root = ("out/window-{0:D2}" -f $Window)
    }
    if ($Kind -eq "worker") {
        $entry["queue_file"] = ("queues/window-{0:D2}.json" -f $Window)
    } else {
        $entry["upstreams"] = @($Upstreams)
    }
    return [pscustomobject]$entry
}

function New-QueueMarkdown {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$WindowEntry,
        [Parameter(Mandatory = $true)]
        [pscustomobject]$QueuePayload
    )

    $lines = @(
        "# Window {0:D2} Queue" -f [int]$WindowEntry.window,
        "",
        "- Name: $($WindowEntry.name)",
        "- Area: $($WindowEntry.area)",
        "- Queue kind: $($QueuePayload.queue_kind)",
        "- Remaining active items: $($QueuePayload.remaining_items)",
        "- Historical completed items removed: $($QueuePayload.completed_items_removed)",
        "- Report: workflow/$($QueuePayload.report_file)",
        "- True north: $($QueuePayload.true_north)",
        "- Queue intent: $($QueuePayload.queue_intent)",
        "- Merge style: $($QueuePayload.merge_style)",
        "- Use bug body lookup: workflow/scripts/get_bug_section.ps1 -BugId BUG-XXX",
        ""
    )

    if ($QueuePayload.PSObject.Properties.Name -contains "preflight_reads") {
        $lines += "- Queue preflight reads:"
        foreach ($path in @($QueuePayload.preflight_reads)) {
            $lines += "  - $path"
        }
        $lines += ""
    }

    if ($QueuePayload.PSObject.Properties.Name -contains "delivery_standard") {
        $lines += "- Delivery standard:"
        foreach ($line in @($QueuePayload.delivery_standard)) {
            $lines += "  - $line"
        }
        $lines += ""
    }

    foreach ($item in @($QueuePayload.items)) {
        $lines += "{0}. {1} | phase {2} | {3} | {4}" -f [int]$item.queue_index, [string]$item.bug_id, [string]$item.phase, [string]$item.severity, [string]$item.title
        $lines += "   files: " + (@($item.files_hint) -join ", ")
        if ($item.PSObject.Properties.Name -contains "mission") {
            $lines += "   mission: " + [string]$item.mission
        }
        if ($item.PSObject.Properties.Name -contains "acceptance_focus") {
            $lines += "   acceptance: " + (@($item.acceptance_focus) -join " | ")
        }
        if ($item.PSObject.Properties.Name -contains "implementation_nexus") {
            $lines += "   nexus: " + (@($item.implementation_nexus) -join " | ")
        }
        $lines += ""
    }

    return ($lines -join "`r`n")
}

function New-WorkerState {
    param(
        [AllowNull()]
        [pscustomobject]$BaseState,
        [Parameter(Mandatory = $true)]
        [pscustomobject]$WindowEntry,
        [Parameter(Mandatory = $true)]
        [int]$RemainingItems,
        [Parameter(Mandatory = $true)]
        [string]$Stamp
    )

    $state = [pscustomobject]@{}
    foreach ($prop in @("last_package_dir", "last_seeded_cycle", "last_seed_package_dir", "archived_history")) {
        $value = $null
        if ($BaseState -and ($BaseState.PSObject.Properties.Name -contains $prop)) {
            $value = $BaseState.$prop
        }
        Set-PropertyValue -Object $state -Name $prop -Value $value
    }

    Set-PropertyValue -Object $state -Name "window" -Value ([int]$WindowEntry.window)
    Set-PropertyValue -Object $state -Name "kind" -Value "worker"
    Set-PropertyValue -Object $state -Name "name" -Value ([string]$WindowEntry.name)
    Set-PropertyValue -Object $state -Name "area" -Value ([string]$WindowEntry.area)
    Set-PropertyValue -Object $state -Name "status" -Value $(if ($RemainingItems -gt 0) { "ready" } else { "complete" })
    Set-PropertyValue -Object $state -Name "history" -Value @()
    Set-PropertyValue -Object $state -Name "completed_count" -Value 0
    Set-PropertyValue -Object $state -Name "current_round" -Value 1
    Set-PropertyValue -Object $state -Name "current_item" -Value $null
    Set-PropertyValue -Object $state -Name "total_items" -Value $RemainingItems
    Set-PropertyValue -Object $state -Name "rebased_utc" -Value $Stamp
    return $state
}

function New-CompilerState {
    param(
        [AllowNull()]
        [pscustomobject]$BaseState,
        [Parameter(Mandatory = $true)]
        [pscustomobject]$WindowEntry,
        [Parameter(Mandatory = $true)]
        [string]$Stamp
    )

    $state = [pscustomobject]@{}
    foreach ($prop in @("last_package_dir", "last_seeded_cycle", "last_seed_package_dir", "archived_history")) {
        $value = $null
        if ($BaseState -and ($BaseState.PSObject.Properties.Name -contains $prop)) {
            $value = $BaseState.$prop
        }
        Set-PropertyValue -Object $state -Name $prop -Value $value
    }

    Set-PropertyValue -Object $state -Name "window" -Value ([int]$WindowEntry.window)
    Set-PropertyValue -Object $state -Name "kind" -Value ([string]$WindowEntry.kind)
    Set-PropertyValue -Object $state -Name "name" -Value ([string]$WindowEntry.name)
    Set-PropertyValue -Object $state -Name "area" -Value ([string]$WindowEntry.area)
    Set-PropertyValue -Object $state -Name "status" -Value "idle"
    Set-PropertyValue -Object $state -Name "history" -Value @()
    Set-PropertyValue -Object $state -Name "completed_rounds" -Value 0
    Set-PropertyValue -Object $state -Name "current_round" -Value 1
    Set-PropertyValue -Object $state -Name "upstreams" -Value @($WindowEntry.upstreams)
    Set-PropertyValue -Object $state -Name "rebased_utc" -Value $Stamp
    return $state
}

$workflowRoot = Split-Path -Parent $PSScriptRoot
$nowUtc = (Get-Date).ToUniversalTime().ToString("o")
$reportFile = "source/XYZGL_MASTER_BUG_REPORT_FINAL_UNIFIED_v27_20260309_120450.md"
$sharedAuditBasis = @(
    "Matched queued BUG IDs against regression tests in tests/test_bug*.py.",
    "Repartitioned the unresolved backlog into the 18-window orchestra while keeping already-implemented work removed from runnable queues.",
    "Added stronger window-level and bug-level guidance so each worker can build toward enterprise-grade reliability, operator trust, and monetizable product value instead of narrow patch memory."
)

$windows = @(
    (New-WindowEntry -Window 1 -Kind "worker" -Name "Runtime Router and Sanitization" -Area "Owns router, protocol, mirror input-output, fallback, and sanitization runtime bugs."),
    (New-WindowEntry -Window 2 -Kind "worker" -Name "Grounding and Prompt Assembly" -Area "Owns grounding corpora, prompt assembly, prompt-budget guards, and grounding-path integrity bugs."),
    (New-WindowEntry -Window 3 -Kind "worker" -Name "Graph, Retrieval Bench, and Curriculum Evidence" -Area "Owns graph persistence, retrieval evidence, retrieval benchmark parity, and curriculum-evidence bugs."),
    (New-WindowEntry -Window 4 -Kind "worker" -Name "Tutor Runtime and Session Logic" -Area "Owns tutor phases, session loop semantics, learner-state continuity, CLI resume, and policy-close behavior."),
    (New-WindowEntry -Window 5 -Kind "worker" -Name "Harness Turn and Artifact Integrity" -Area "Owns harness_turn behavior, turn artifacts, witness event identity, and turn-facing run path bugs."),
    (New-WindowEntry -Window 6 -Kind "worker" -Name "Session Harness and Determinism Plumbing" -Area "Owns harness_session, seed sweep, run path, determinism controls, and session-export auditability bugs."),
    (New-WindowEntry -Window 7 -Kind "worker" -Name "Replay Diff and Bundle Integrity" -Area "Owns replay-diff behavior, strict replay semantics, and replay-facing bundle integrity bugs."),
    (New-WindowEntry -Window 8 -Kind "worker" -Name "Sweep Orchestration and Repo Safety" -Area "Owns targeted sweep execution, cadence verification, repo cleanliness, and deterministic run-path orchestration bugs."),
    (New-WindowEntry -Window 9 -Kind "worker" -Name "Schema Gates and CI Bundle Routing" -Area "Owns canonical artifact schemas, CI gate routing, smoke-report identity, and run-bundle completeness bugs."),
    (New-WindowEntry -Window 10 -Kind "worker" -Name "Artifact Roundtrip and Canonical Repair" -Area "Owns artifact roundtrip strictness, direct-file repair, nested child-run traversal, and canonical run-bundle rewrite bugs."),
    (New-WindowEntry -Window 11 -Kind "worker" -Name "Workflow Companion and Prompt Governance" -Area "Owns prompt snapshot guards, citation guards, signal-fidelity tooling, and doc-code workflow contract bugs."),
    (New-WindowEntry -Window 12 -Kind "worker" -Name "Detectors, Scanners, and Drift Radar" -Area "Owns secret scanning, drift radar, graph invariants, mirror leakage, and detector-fidelity bugs."),
    (New-WindowEntry -Window 13 -Kind "worker" -Name "Backend Probes and Fault Injection" -Area "Owns backend contract probes, backend fault injectors, and backend-side validation bugs."),
    (New-WindowEntry -Window 14 -Kind "worker" -Name "Fuzzer Core and Coverage Truthfulness" -Area "Owns property and fuzz harnesses that must report canonical artifacts, real coverage, and replayable failing evidence."),
    (New-WindowEntry -Window 15 -Kind "worker" -Name "Lattice, Benches, and Adversarial Suites" -Area "Owns sensitivity benches, calibration harnesses, and adversarial suites that must fail closed instead of reporting false green."),
    (New-WindowEntry -Window 16 -Kind "precompile" -Name "Runtime and Core Precompiler" -Area "Precompiles worker outputs from windows 1 through 7 into one cumulative runtime stream." -Upstreams @(1, 2, 3, 4, 5, 6, 7)),
    (New-WindowEntry -Window 17 -Kind "precompile" -Name "Tooling and Guardrail Precompiler" -Area "Precompiles worker outputs from windows 8 through 15 into one cumulative tooling and guardrail stream." -Upstreams @(8, 9, 10, 11, 12, 13, 14, 15)),
    (New-WindowEntry -Window 18 -Kind "final" -Name "Final Compiler" -Area "Merges windows 16 and 17 into the final cumulative integrated package stream for the current cycle." -Upstreams @(16, 17))
)

$fullAssignments = @{
    1 = @("BUG-146", "BUG-109", "BUG-01", "BUG-02", "BUG-05", "BUG-06", "BUG-27", "BUG-28", "BUG-54", "BUG-75", "BUG-83", "BUG-95", "BUG-103")
    2 = @("BUG-110", "BUG-03", "BUG-19", "BUG-20", "BUG-48", "BUG-58", "BUG-69", "BUG-80", "BUG-88", "BUG-92", "BUG-102")
    3 = @("BUG-148", "BUG-135", "BUG-132", "BUG-59", "BUG-21", "BUG-46", "BUG-47", "BUG-70", "BUG-93", "BUG-99")
    4 = @("BUG-141", "BUG-128", "BUG-129", "BUG-121", "BUG-04", "BUG-100", "BUG-07", "BUG-08", "BUG-09", "BUG-89")
    5 = @("BUG-10", "BUG-11", "BUG-23", "BUG-24", "BUG-37", "BUG-49", "BUG-86", "BUG-60", "BUG-62", "BUG-61")
    6 = @("BUG-140", "BUG-85", "BUG-12", "BUG-13", "BUG-32", "BUG-33", "BUG-43", "BUG-50", "BUG-52", "BUG-55", "BUG-82", "BUG-84")
    7 = @("BUG-133", "BUG-117", "BUG-111", "BUG-14", "BUG-15", "BUG-16", "BUG-65", "BUG-72", "BUG-74", "BUG-90", "BUG-104")
    8 = @("BUG-147", "BUG-142", "BUG-127", "BUG-123", "BUG-119", "BUG-31", "BUG-45", "BUG-67")
    9 = @("BUG-144", "BUG-137", "BUG-120", "BUG-116", "BUG-114", "BUG-112", "BUG-113", "BUG-76")
    10 = @("BUG-134", "BUG-78", "BUG-79", "BUG-81", "BUG-94")
    11 = @("BUG-149", "BUG-145", "BUG-126", "BUG-122", "BUG-22", "BUG-38", "BUG-41", "BUG-42", "BUG-53", "BUG-77", "BUG-105", "BUG-108")
    12 = @("BUG-143", "BUG-139", "BUG-136", "BUG-130", "BUG-118", "BUG-115", "BUG-17", "BUG-18", "BUG-26", "BUG-64", "BUG-66", "BUG-71", "BUG-73", "BUG-106", "BUG-107")
    13 = @("BUG-51", "BUG-29", "BUG-30", "BUG-39", "BUG-40", "BUG-56", "BUG-57", "BUG-91", "BUG-97")
    14 = @("BUG-124", "BUG-125", "BUG-87", "BUG-25", "BUG-34", "BUG-35", "BUG-36", "BUG-44", "BUG-63", "BUG-68")
    15 = @("BUG-131", "BUG-138", "BUG-96", "BUG-98", "BUG-101")
}

$windowGuidance = @{
    1 = [ordered]@{
        true_north = "Fail closed on protocol and backend-contract ambiguity so the tutor runtime never silently degrades into an un-auditable path."
        queue_intent = "These fixes protect protocol authority, backend metadata integrity, and artifact-safe runtime execution."
        merge_style = "Prefer narrow contract checks at runtime boundaries and keep behavior deterministic under strict mode."
        preflight_reads = @("NORTH_STAR.md", "STABLE/WITNESS_PROTOCOL_v2.1.md", "xyzgl/router.py", "xyzgl/orchestrator/tutor_phases.py")
        delivery_standard = @("Reject malformed or semantically invalid runtime inputs explicitly.", "Preserve replayability and UTF-8-safe artifact emission.", "Add regression coverage at the entry point that previously fail-opened.")
    }
    2 = [ordered]@{
        true_north = "Grounding must remain structurally faithful across path formats, paragraph boundaries, and prompt-budget settings."
        queue_intent = "These fixes defend grounding integrity before corrupted context can poison prompt assembly."
        merge_style = "Normalize early, clamp once, and make path handling portable across Windows and POSIX."
        preflight_reads = @("NORTH_STAR.md", "xyzgl/grounding/corpus.py", "xyzgl/prompting.py", "xyzgl/config.py")
        delivery_standard = @("Never silently drop valid grounding inputs.", "Keep prompt budget calculations single-sourced.", "Use tests that prove both corpus parsing and prompt construction stay aligned.")
    }
    3 = [ordered]@{
        true_north = "Retrieval evidence must show the real supporting passage instead of a cosmetically plausible excerpt."
        queue_intent = "These fixes improve retrieval truthfulness, boundary handling, and benchmark input validation."
        merge_style = "Bias toward evidence fidelity over optimistic scoring or convenience shortcuts."
        preflight_reads = @("NORTH_STAR.md", "xyzgl/grounding/retrieval.py", "tools/retrieval_eval_bench.py", "xyzgl/grounding/corpus.py")
        delivery_standard = @("Shown evidence must contain the actual matched content.", "Malformed benchmark rows must fail early with useful diagnostics.", "Chunking changes must preserve deterministic retrieval behavior.")
    }
    4 = [ordered]@{
        true_north = "The learner session must remain continuous and auditable across turns."
        queue_intent = "This queue protects the canonical tutoring loop from losing state or mis-sequencing phase behavior."
        merge_style = "Prefer state continuity and explicit turn lineage over hidden resets."
        preflight_reads = @("NORTH_STAR.md", "xyzgl/orchestrator/session_loop.py", "xyzgl/orchestrator/tutor_phases.py")
        delivery_standard = @("Carry forward the real conversational state that drove the tutor.", "Keep exported artifacts consistent with the runtime path.", "Regression tests should span at least two turns.")
    }
    5 = [ordered]@{
        true_north = "Harness turn artifacts must remain canonical and attributable to the exact executed witness path."
        queue_intent = "This queue stays complete only when single-turn harness outputs are stable, canonical, and attributable."
        merge_style = "Treat artifact identity fields as contracts, not cosmetic metadata."
        preflight_reads = @("NORTH_STAR.md", "tools/harness_turn.py", "witness/core.py")
        delivery_standard = @("The exported bundle must describe the exact run that happened.", "Identifiers must be stable under replay.", "Docs, tests, and emitted schemas must agree.")
    }
    6 = [ordered]@{
        true_north = "Session tooling must preserve determinism, privacy controls, and truthful run provenance across every exported artifact."
        queue_intent = "These fixes protect seed lineage, mirror governance, run-root resolution, and learner-state truthfulness."
        merge_style = "Favor auditable provenance over convenience defaults tied to cwd or CLI shortcuts."
        preflight_reads = @("NORTH_STAR.md", "tools/harness_session.py", "tools/seed_sweep.py", "tools/run_paths.py", "xyzgl/orchestrator/session_loop.py")
        delivery_standard = @("Run identity must reflect the real workload, not a brittle placeholder.", "Privacy and mirror controls must propagate through all tooling layers.", "Artifacts must tell the truth about the learner state that actually drove tutoring.")
    }
    7 = [ordered]@{
        true_north = "Replay-diff tools must detect drift across the full bundle, not just the most obvious top-level files."
        queue_intent = "These fixes keep replay comparison strict enough to catch hidden schema or identity regressions."
        merge_style = "Compare cross-file identities and inner payload fields, not only filenames."
        preflight_reads = @("NORTH_STAR.md", "tools/repro_replay_diff.py")
        delivery_standard = @("Bundle diffing must detect nested metadata drift.", "A green replay result must mean semantic parity, not superficial filename parity.", "Tests should include mutated inner fields.")
    }
    8 = [ordered]@{
        true_north = "Sweep orchestration must be deterministic, repo-safe, and honest about where it wrote or found artifacts."
        queue_intent = "This queue hardens targeted sweep execution, doctor preflight ordering, and run-path extraction."
        merge_style = "Keep orchestrators clean-room: do not mutate the repo or erase the child process breadcrumbs needed for audit."
        preflight_reads = @("NORTH_STAR.md", "tools/targeted_sweep.py", "tools/doctor.py", "tools/reground_cadence_verifier.py")
        delivery_standard = @("Forward determinism and path flags all the way into child tools.", "Do not sanitize away the exact run paths the parent needs.", "Repo validation must happen before any contaminating writes.")
    }
    9 = [ordered]@{
        true_north = "Schemas and CI gates must certify the real artifact graph, not a partial or mislabeled bundle."
        queue_intent = "These bugs all weaken canonical artifact naming, schema identity, or CI bundle completeness."
        merge_style = "Prefer bundle completeness checks and canonical names over permissive validation."
        preflight_reads = @("NORTH_STAR.md", "tools/validate_schemas.py", "tools/ci_gate.py", "tools/coverage_gate.py", "tools/repro_backends_smoke.py")
        delivery_standard = @("If an artifact is emitted, it must be declared and schema-correct.", "CI must fail for real secret or scaffold issues, not report the wrong cause.", "Smoke reports must never impersonate another tool's schema.")
    }
    10 = [ordered]@{
        true_north = "Roundtrip tooling must repair and validate the entire artifact tree, including nested child runs and strict failure propagation."
        queue_intent = "These items all protect the strict roundtrip checker from missing or misreporting real bundle defects."
        merge_style = "Treat strict mode as an end-to-end truth contract, not a best-effort convenience pass."
        preflight_reads = @("NORTH_STAR.md", "tools/artifact_roundtrip.py")
        delivery_standard = @("Nested child artifacts must participate in traversal and repair.", "Process-level FAIL must never leave per-file PASS markers behind.", "Direct-file repair support must match the advertised CLI contract.")
    }
    11 = [ordered]@{
        true_north = "Workflow companion tools must preserve prompt, citation, and doc-code governance instead of drifting into stale or self-contradictory behavior."
        queue_intent = "This queue modernizes prompt guardrails, citation tooling, signal-fidelity support, and workflow companion contracts."
        merge_style = "One source of truth per contract: prompt baselines, docs, and companion tooling must agree."
        preflight_reads = @("NORTH_STAR.md", "tools/prompt_snapshot_guard.py", "tools/grounding_injection_audit.py", "tools/doc_code_link_checker.py", "documentation/tools/")
        delivery_standard = @("Guard tools must reject malformed or missing support assets before claiming success.", "Docs and code must move together.", "Environment sensitivity should be isolated behind explicit gates or fixtures.")
    }
    12 = [ordered]@{
        true_north = "Detector suites must surface the highest-signal failures without leaking secrets, paths, or false-green assurances."
        queue_intent = "These fixes harden scanners and drift detectors against blind spots, stale regexes, and severity inversions."
        merge_style = "Fail closed on malformed evidence and preserve severity ordering when truncating reports."
        preflight_reads = @("NORTH_STAR.md", "tools/secret_scanner.py", "tools/protocol_drift_radar.py", "tools/graph_invariant_checker.py", "tools/mirror_leakage_detector.py")
        delivery_standard = @("Large or oddly formatted files must still be scanned intentionally.", "Severity caps must not hide later HIGH findings.", "Reports must not trust user-provided labels over embedded artifact truth.")
    }
    13 = [ordered]@{
        true_north = "Backend probe tooling must reveal real contract failures and side effects before the system trusts a backend."
        queue_intent = "This queue keeps backend contract probes and fault injectors fail-closed, side-effect-aware, and network-safe."
        merge_style = "Validate backend construction prerequisites before backend instantiation and preserve stderr/stdout side effects in the final judgment."
        preflight_reads = @("NORTH_STAR.md", "tools/backend_contract_probe.py", "tools/backend_fault_injector.py")
        delivery_standard = @("A PASS result must mean a real probe occurred.", "Backend-side leaks and side effects must be part of the verdict.", "Offline gating must happen before any backend object can misclassify the environment.")
    }
    14 = [ordered]@{
        true_north = "Fuzzer outputs must be canonical, coverage claims must be honest, and failing evidence must remain replayable."
        queue_intent = "This queue hardens property and fuzz harnesses so they expose the real exercised space instead of a flattering approximation."
        merge_style = "Bias toward truthful failing artifacts and explicit counterexamples over optimistic coverage headlines."
        preflight_reads = @("NORTH_STAR.md", "tools/property_turn_fuzzer.py", "tools/atheris_fuzz_router.py", "xyzgl/router.py")
        delivery_standard = @("Run bundles must remain canonical even on incomplete or failing paths.", "Coverage metrics must correspond to the true exercised branch space.", "Counterexamples and failing payloads must survive export.")
    }
    15 = [ordered]@{
        true_north = "Sensitivity and adversarial suites must prove meaningful behavioral movement rather than reporting empty green checks."
        queue_intent = "These tasks tighten lattice semantics, calibration benches, and adversarial boundary suites."
        merge_style = "Require meaningful semantic movement and robust malformed-input handling before a suite can report PASS."
        preflight_reads = @("NORTH_STAR.md", "tools/harness_lattice.py", "tools/lattice_lib.py", "tools/redteam_rag_poisoning_suite.py", "tools/mirror_calibration_bench.py")
        delivery_standard = @("False-green benchmark passes are worse than explicit failures.", "Boundary checks must reject malformed structured layouts.", "Bench outputs should prove behavior changed for the tested dimension.")
    }
}

$bugStrategy = @{
    "BUG-27" = [ordered]@{
        mission = "Turn invalid protocol paths into explicit, auditable failure handling instead of a silent downgrade. Emit a stable reason code or artifact signal so hosted support and compliance tooling can classify the fault without manual log digging."
        implementation_nexus = @("Validate configured protocol path existence and readability before fallback selection.", "Keep any permissive fallback behind an explicit policy branch with a test.")
        acceptance_focus = @("An invalid configured protocol path does not quietly select fallback protocol content.", "Regression proves the emitted error or fallback path is deterministic and inspectable.")
    }
    "BUG-54" = [ordered]@{
        mission = "Reject empty tutor output before later phases normalize it into a fake success. Preserve enough structured context that premium monitoring can distinguish model blanking from downstream parser or transport failures."
        implementation_nexus = @("Treat blank or whitespace-only tutor output as invalid at the parsing boundary.", "Propagate a structured failure that preserves debugging context.")
        acceptance_focus = @("Probe and eval phases both fail closed on empty tutor output.", "Tests assert no downstream PASS artifact is emitted from empty model output.")
    }
    "BUG-83" = [ordered]@{
        mission = "Stop accepting semantically invalid backend metadata as runtime success. Make the invalid field and verdict visible in artifacts so operators can remediate configuration defects without reproducing the run interactively."
        implementation_nexus = @("Validate backend metadata fields even when no exception was thrown.", "Keep strict mode aligned with semantic validity, not only crash behavior.")
        acceptance_focus = @("Strict mode fails for malformed backend metadata values.", "The router and runtime surfaces agree on the invalid contract verdict.")
    }
    "BUG-103" = [ordered]@{
        mission = "Make backend strings UTF-8-safe before probes and artifact emission diverge. Force the runtime, probes, and artifact writers onto one validation contract so enterprise certification cannot pass a backend that later crashes during export."
        implementation_nexus = @("Normalize or reject backend strings before witness/artifact paths consume them.", "Keep tools and runtime on the same backend-name validation path.")
        acceptance_focus = @("A backend string that would crash artifact emission cannot still produce a green probe.", "Tests cover both probe tooling and runtime artifact creation.")
    }
    "BUG-80" = [ordered]@{
        mission = "Preserve paragraph boundaries so poisoned and clean grounding passages cannot collapse together. Keep the split rules simple and portable so commercial grounding packs behave the same way across authoring pipelines and operating systems."
        implementation_nexus = @("Treat whitespace-only blank lines as structural paragraph breaks.", "Keep chunking stable after normalization.")
        acceptance_focus = @("Whitespace-only separators still split grounding paragraphs.", "Oversized merged paragraphs no longer appear from blank-line-only separators.")
    }
    "BUG-92" = [ordered]@{
        mission = "Make manifest source path normalization portable across Windows and POSIX. Ensure the normalized path contract is deterministic enough for packaged curriculum assets and customer-provided corpora to round-trip cleanly."
        implementation_nexus = @("Normalize separators before manifest lookups.", "Avoid dropping valid sources because of host-specific slash conventions.")
        acceptance_focus = @("Windows-style manifest paths resolve on POSIX.", "Grounding source manifests stay intact across platforms.")
    }
    "BUG-102" = [ordered]@{
        mission = "Remove the hidden re-clamp so prompt assembly and direct grounding agree on snippet budget. Give operators one trustworthy knob for grounding spend, latency, and answer richness instead of hidden prompt-budget drift."
        implementation_nexus = @("Use a single authoritative clamp path for grounding_max_snippets.", "Audit dependent tools so they all observe the same configured ceiling.")
        acceptance_focus = @("Prompt assembly respects the configured snippet cap instead of silently forcing 64.", "Audit tools that compare prompt vs grounding outputs remain consistent.")
    }
    "BUG-70" = [ordered]@{
        mission = "Repair chunk boundary logic so evidence at passage edges remains retrievable. Preserve deterministic chunk identities so benchmark baselines and paid evaluation packs do not churn after the fix."
        implementation_nexus = @("Soften no-overlap splitting enough to preserve boundary evidence.", "Keep chunk identity deterministic after the change.")
        acceptance_focus = @("Retrieval succeeds for boundary-spanning evidence that previously disappeared.", "Chunking remains deterministic for the same corpus and config.")
    }
    "BUG-93" = [ordered]@{
        mission = "Make shown retrieval excerpts contain the actual matched evidence. The displayed snippet should be support-grade proof that can be shown to a customer or reviewer without a second forensic lookup."
        implementation_nexus = @("Bind displayed excerpt generation to the real matching span.", "Prevent certification when the displayed excerpt omits the proof.")
        acceptance_focus = @("Certified snippets show the text that justified the match.", "Evaluation cannot green-light an excerpt that hides the evidence.")
    }
    "BUG-99" = [ordered]@{
        mission = "Validate benchmark row field types before retrieval evaluation trusts them. Replace late crashes and false passes with crisp contract failures that make external benchmark packs safe to sell, share, and automate."
        implementation_nexus = @("Fail early on malformed benchmark row types.", "Keep malformed rows from false-passing or crashing late.")
        acceptance_focus = @("Malformed benchmark rows produce clear validation failures.", "Evaluation no longer falsely passes because of implicit coercion.")
    }
    "BUG-09" = [ordered]@{
        mission = "Preserve conversational continuity across turns in the session orchestrator. Make the continuity explicit enough that longitudinal tutoring features and customer-facing session exports can be trusted as a product surface, not just a debug trace."
        implementation_nexus = @("Carry forward the learner context and tutor state that the next turn depends on.", "Keep exported artifacts aligned with the actual turn-to-turn state.")
        acceptance_focus = @("Multi-turn tests retain the expected prior-turn context.", "Exported session artifacts describe the same continuity the runtime used.")
    }
    "BUG-50" = [ordered]@{
        mission = "Propagate mirror enablement and privacy controls through every session tool and artifact. Treat those controls as billable trust features whose effective state must stay inspectable from CLI to final export."
        implementation_nexus = @("Push mirror/privacy flags through harness_session, seed_sweep, and runtime plumbing.", "Record those controls in exported artifacts so auditors can verify them.")
        acceptance_focus = @("Mirror/privacy settings survive tool-to-tool handoff.", "Artifacts show the effective mirror/privacy state that drove execution.")
    }
    "BUG-52" = [ordered]@{
        mission = "Make sweep run identity depend on the actual workload, not only the seed integer. Stable but truthful run identity makes comparison dashboards, customer reports, and support escalations materially more useful."
        implementation_nexus = @("Derive run identity from workload shape as well as seed.", "Keep deterministic replay stable for the same workload.")
        acceptance_focus = @("Changing workload with the same seed changes run identity appropriately.", "Re-running the same workload and seed keeps the same identity.")
    }
    "BUG-55" = [ordered]@{
        mission = "Resolve runs roots against the tool contract instead of the caller's cwd. That path contract should be reliable enough for scheduled jobs, CI runners, and customer-hosted automation to use without wrapper scripts."
        implementation_nexus = @("Anchor default and relative run roots to a stable base path.", "Keep tooling behavior portable across invocation contexts.")
        acceptance_focus = @("The same command resolves the same run root from different cwd values.", "Harness and sweep tools agree on where runs live.")
    }
    "BUG-82" = [ordered]@{
        mission = "Tell the truth about the learner state and active tutoring branch in session artifacts. The exported narrative should be accurate enough to power premium analytics, instructor review, and customer success triage."
        implementation_nexus = @("Export the learner state that actually drove tutoring.", "Revive or remove dead stub-tutor branches so artifacts cannot claim nonexistent behavior.")
        acceptance_focus = @("Session artifacts report the real learner state and branch taken.", "The flow vs frustrated branch is either exercised truthfully or no longer falsely implied.")
    }
    "BUG-90" = [ordered]@{
        mission = "Catch run.json issue_id drift across files inside replay bundles. Replay verdicts should be strong enough that teams can trust a green status in paid support and regression review workflows."
        implementation_nexus = @("Compare cross-file issue identity, not only local file content.", "Keep bundle validation strict across nested artifacts.")
        acceptance_focus = @("Replay diff flags mismatched issue ids anywhere in the bundle.", "A green result requires cross-file identity parity.")
    }
    "BUG-104" = [ordered]@{
        mission = "Catch schema-version drift hidden inside session bundle payloads. Make semantic drift visible early so bundle consumers and downstream integrations do not discover incompatibilities after shipment."
        implementation_nexus = @("Inspect inner payload.session_report.schema_version values.", "Do not stop at top-level file naming parity.")
        acceptance_focus = @("Replay diff flags inner schema_version drift.", "Nested payload metadata participates in semantic diffing.")
    }
    "BUG-45" = [ordered]@{
        mission = "Preserve raw child output long enough to extract the run paths it contains. Keep the safe-output path compatible with production logging while still preserving the audit breadcrumbs that make sweep artifacts commercially supportable."
        implementation_nexus = @("Separate path extraction from cosmetic output sanitization.", "Only sanitize after the parent has captured the child bundle location.")
        acceptance_focus = @("targeted_sweep still finds child run paths after sanitization changes.", "Diagnostics remain safe without erasing the path signal.")
    }
    "BUG-67" = [ordered]@{
        mission = "Run repo health checks before targeted_sweep contaminates the working tree. This should make the tool safe for premium CI and customer demo environments where false repo dirtiness destroys confidence."
        implementation_nexus = @("Move doctor or cleanliness checks ahead of any write-producing step.", "Keep sweep setup from masking the repo state it was supposed to verify.")
        acceptance_focus = @("doctor sees the real pre-sweep repo state.", "targeted_sweep no longer dirties the repo before validation.")
    }
    "BUG-113" = [ordered]@{
        mission = "Stop smoke tools from impersonating other tools' report names or schema identities. Every emitted report should be reliable enough to feed billing, compliance, and support pipelines without manual relabeling."
        implementation_nexus = @("Bind report filenames and schema_version fields to the emitting tool.", "Teach validate_schemas to reject cross-tool identity mismatches.")
        acceptance_focus = @("Smoke artifacts carry their own canonical name and schema.", "Schema validation rejects mismatched tool identities.")
    }
    "BUG-76" = [ordered]@{
        mission = "Keep ci_gate from losing the child run directory it just created. The fix should make CI failures self-serve, so a paying team can inspect the exact bundle without reproducing the job."
        implementation_nexus = @("Extract run directory before any stdout sanitization step.", "Keep ci_gate's run-bundle lookup tied to the actual child output.")
        acceptance_focus = @("ci_gate can locate its created run bundle after sanitization.", "The fix does not reintroduce unsafe child-output handling.")
    }
    "BUG-79" = [ordered]@{
        mission = "Traverse nested child_runs JSON files during roundtrip checks and repair. Treat nested artifacts as first-class billable evidence, not optional debris, so full-fidelity run bundles stay dependable."
        implementation_nexus = @("Treat nested child_runs as first-class bundle members.", "Use the same traversal rules in validation and fix modes.")
        acceptance_focus = @("artifact_roundtrip sees nested child_runs JSON files.", "Directing the tool at a run directory covers nested artifacts end to end.")
    }
    "BUG-94" = [ordered]@{
        mission = "Align strict-mode process verdicts with per-file verdicts. A premium-quality strict report must read like a single coherent judgment, not a contradiction that forces human arbitration."
        implementation_nexus = @("Do not let a process-level FAIL coexist with lingering PASS markers on changed files.", "Keep strict-mode reporting internally consistent.")
        acceptance_focus = @("A strict FAIL leaves no contradictory PASS markers on changed files.", "The emitted artifact clearly reflects the single final verdict.")
    }
    "BUG-42" = [ordered]@{
        mission = "Make grounding injection audit results stable across environments. Deterministic audit behavior is what turns the tool from an internal helper into a credible customer-facing assurance check."
        implementation_nexus = @("Isolate environment-dependent factors behind explicit setup or fixtures.", "Keep failure attribution tied to the real grounding defect, not host noise.")
        acceptance_focus = @("The same test case yields the same verdict across supported environments.", "Failure messages point at the actual cause rather than setup variance.")
    }
    "BUG-53" = [ordered]@{
        mission = "Ship the required companion docs alongside signal_fidelity_port. Treat the docs as part of the sellable feature so operators can adopt the tool without reading source or reverse-engineering hidden assumptions."
        implementation_nexus = @("Add or regenerate the missing doc artifacts and wire doc-code checks to them.", "Keep tool help, docs, and doc-link checks in sync.")
        acceptance_focus = @("Required companion docs exist and pass doc-code link checks.", "Tool-facing docs describe the real shipped behavior.")
    }
    "BUG-77" = [ordered]@{
        mission = "Stop defaulting to an overlay archive that the repo does not ship. A first-run experience that works out of the box is critical if the tool is going to feel productized rather than hand-held."
        implementation_nexus = @("Point defaults at a shipped asset or require explicit input.", "Make docs and CLI help reflect the real default behavior.")
        acceptance_focus = @("Default execution works without referencing a nonexistent overlay archive.", "Documentation matches the actual default path.")
    }
    "BUG-96" = [ordered]@{
        mission = "Require harness_lattice to prove meaningful semantic movement across lattice dimensions. Turn the suite into a decision-grade benchmark that can justify tuning, procurement, and premium quality claims."
        implementation_nexus = @("Measure whether dimension changes alter reply meaningfully, not only mechanically.", "Fail closed when the sweep produces no substantive behavioral delta.")
        acceptance_focus = @("A false-green sweep with identical meanings now fails or warns explicitly.", "Reported lattice findings demonstrate real semantic change.")
    }
    "BUG-64" = [ordered]@{
        mission = "Scan large text files intentionally instead of silently skipping them. Large-corpus trust is part of the commercial value proposition, so the scanner must never fail open on the files customers care about most."
        implementation_nexus = @("Replace the silent size skip with bounded scanning or an explicit surfaced verdict.", "Keep performance controls observable rather than invisible.")
        acceptance_focus = @("Large text files no longer disappear from secret scanning without a verdict.", "Regression proves the scanner still handles large files predictably.")
    }
    "BUG-73" = [ordered]@{
        mission = "Teach protocol_drift_radar to inspect session_summary.md when scanning directories. Expand the scan so the summary surface becomes a dependable review artifact rather than a blind spot in premium audit workflows."
        implementation_nexus = @("Include session_summary.md in the directory scan artifact set.", "Keep the added surface aligned with existing drift heuristics.")
        acceptance_focus = @("Directory scans include session_summary.md findings.", "The added coverage does not break existing scan semantics.")
    }
    "BUG-91" = [ordered]@{
        mission = "Treat stdout/stderr side effects as first-class backend validation evidence. Side-effect truthfulness is what keeps backend certification credible in regulated or customer-hosted environments."
        implementation_nexus = @("Capture and judge side effects instead of hiding them behind green or handled outcomes.", "Prevent secret-bearing output from becoming an invisible side channel.")
        acceptance_focus = @("Secret-bearing or unsafe side effects affect the final probe verdict.", "Backend validation reports include side-effect-aware reasoning.")
    }
    "BUG-97" = [ordered]@{
        mission = "Run the no-network gate before backend construction can misclassify the environment. Clean defect classification makes the probe more supportable and keeps offline SKUs from looking broken for the wrong reason."
        implementation_nexus = @("Move offline/local gating ahead of backend object creation.", "Keep offline misconfiguration distinct from post-construction backend failures.")
        acceptance_focus = @("Offline and local backend defects are classified correctly before backend construction.", "The probe no longer mislabels network-gated environments.")
    }
    "BUG-34" = [ordered]@{
        mission = "Make property_turn_fuzzer emit canonical run.json artifacts. The emitted bundle should be production-grade evidence that can flow through the same tooling, dashboards, and paid assurance workflows as any other run."
        implementation_nexus = @("Align the fuzzer's bundle writer with canonical run.json expectations.", "Keep incomplete or failing paths canonical as well.")
        acceptance_focus = @("Fuzzer run.json matches canonical schema and field expectations.", "Roundtrip or schema validation accepts the emitted bundle without fix-up.")
    }
    "BUG-35" = [ordered]@{
        mission = "Reach the welding-specific single-turn branch from the turn fuzzer. Create proof that the domain-critical branch is truly exercised, so the coverage story maps to the product customers are buying."
        implementation_nexus = @("Generate inputs that can actually drive the welding-specific branch.", "Keep the route selection explicit in the produced evidence.")
        acceptance_focus = @("Fuzzer coverage includes the welding-specific single-turn branch.", "Artifacts prove the targeted branch was exercised.")
    }
    "BUG-36" = [ordered]@{
        mission = "Generate the known control and Unicode stressors that the fuzzer currently misses. This should harden the tutor for messy real-world inputs that show up in international and enterprise deployments."
        implementation_nexus = @("Expand case generation to cover control and Unicode edge inputs.", "Preserve determinism for the same seed and generator config.")
        acceptance_focus = @("The fuzzer now emits the targeted control and Unicode stressors.", "Generated evidence remains replayable and deterministic.")
    }
    "BUG-44" = [ordered]@{
        mission = "Keep evidence and schema canonical even on incomplete fuzzer paths. Failed paths should still produce support-ready artifacts that accelerate debugging instead of becoming expensive dead ends."
        implementation_nexus = @("Do not truncate away the failing evidence needed for replay.", "Preserve canonical schema shape on incomplete execution.")
        acceptance_focus = @("Incomplete fuzzer paths still emit canonical schema.", "Exported evidence retains the information needed to reproduce the failure.")
    }
    "BUG-63" = [ordered]@{
        mission = "Bring ai_property_turn_fuzzer.md back into sync with real tool outputs. Make the documentation good enough to sell the feature and onboard a new operator without side-channel explanation."
        implementation_nexus = @("Update the docs to reflect the actual shipped output contract after the code fix.", "Keep doc drift from reappearing by checking the real output surface.")
        acceptance_focus = @("The doc examples and field descriptions match the tool's actual outputs.", "Doc-code drift tests or checks stay green.")
    }
    "BUG-68" = [ordered]@{
        mission = "Stop overstating coverage when max-len is zero. Honest coverage claims are part of the product's credibility, especially when the artifact may be shown to customers, auditors, or buyers."
        implementation_nexus = @("Treat max-len=0 as a distinct edge case with honest coverage reporting.", "Do not let skipped generation masquerade as exercised space.")
        acceptance_focus = @("Coverage claims for max-len=0 reflect the actual generated workload.", "The tool no longer reports inflated coverage from a degenerate case.")
    }
    "BUG-98" = [ordered]@{
        mission = "Reject malformed structured prompt layouts in the RAG poisoning boundary suite. The boundary suite should behave like a hard security product, not a permissive demo that rewards malformed attack inputs with PASS."
        implementation_nexus = @("Tighten boundary-check input validation before PASS evaluation.", "Make malformed structured layouts fail closed instead of falling through as acceptable.")
        acceptance_focus = @("Malformed structured prompt layouts are rejected or reported as failures.", "PASS is reserved for genuinely valid boundary cases.")
    }
}

$queueByWindow = @{}
$existingItemByBug = @{}
$existingStates = @{}

foreach ($i in 1..16) {
    $queuePath = Join-Path $workflowRoot ("queues/window-{0:D2}.json" -f $i)
    $statePath = Join-Path $workflowRoot ("state/window-{0:D2}.json" -f $i)
    if (-not (Test-Path -LiteralPath $queuePath)) {
        continue
    }
    $queuePayload = Get-Content -Raw $queuePath | ConvertFrom-Json
    $statePayload = Read-JsonFileIfExists -Path $statePath
    $queueByWindow[$i] = $queuePayload
    if ($statePayload) {
        $existingStates[$i] = $statePayload
    }
    foreach ($item in @($queuePayload.items)) {
        $existingItemByBug[[string]$item.bug_id] = [pscustomobject]@{
            source_window = $i
            item = $item
        }
    }
}
$state16 = Read-JsonFileIfExists -Path (Join-Path $workflowRoot "state/window-16.json")
$state17 = Read-JsonFileIfExists -Path (Join-Path $workflowRoot "state/window-17.json")
$state18 = Read-JsonFileIfExists -Path (Join-Path $workflowRoot "state/window-18.json")
$state19 = Read-JsonFileIfExists -Path (Join-Path $workflowRoot "state/window-19.json")
if ($state16) { $existingStates[16] = $state16 }
if ($state17) { $existingStates[17] = $state17 }
if ($state18) { $existingStates[18] = $state18 }
if ($state19) { $existingStates[19] = $state19 }

foreach ($entry in @($windows | Where-Object { $_.kind -eq "worker" } | Sort-Object window)) {
    $windowNumber = [int]$entry.window
    $guidance = $windowGuidance[$windowNumber]
    $sourceItems = @()

    foreach ($bugId in @($fullAssignments[$windowNumber])) {
        if ($existingItemByBug.ContainsKey($bugId)) {
            $sourceItems += $existingItemByBug[$bugId]
        }
    }

    $items = @()
    for ($idx = 0; $idx -lt $sourceItems.Count; $idx++) {
        $sourceInfo = $sourceItems[$idx]
        $sourceItem = $sourceInfo.item
        $sourceWindow = [int]$sourceInfo.source_window
        $strategy = $bugStrategy[[string]$sourceItem.bug_id]

        $payload = [ordered]@{
            queue_index = $idx + 1
            original_queue_index = if ($sourceItem.PSObject.Properties.Name -contains "original_queue_index") { [int]$sourceItem.original_queue_index } else { [int]$sourceItem.queue_index }
            bug_id = [string]$sourceItem.bug_id
            title = [string]$sourceItem.title
            phase = [string]$sourceItem.phase
            severity = [string]$sourceItem.severity
            files_hint = @($sourceItem.files_hint)
            legacy_window = $sourceWindow
            legacy_queue_index = if ($sourceItem.PSObject.Properties.Name -contains "queue_index") { [int]$sourceItem.queue_index } else { $idx + 1 }
        }

        if ($strategy) {
            $payload["mission"] = [string]$strategy.mission
            $payload["implementation_nexus"] = @($strategy.implementation_nexus)
            $payload["acceptance_focus"] = @($strategy.acceptance_focus)
        }

        $items += [pscustomobject]$payload
    }

    $completedRemoved = @($fullAssignments[$windowNumber]).Count - $items.Count
    $queuePayload = [ordered]@{
        window = $windowNumber
        name = [string]$entry.name
        area = [string]$entry.area
        report_file = $reportFile
        audited_utc = $nowUtc
        audit_basis = $sharedAuditBasis
        true_north = [string]$guidance.true_north
        queue_intent = [string]$guidance.queue_intent
        merge_style = [string]$guidance.merge_style
        preflight_reads = @($guidance.preflight_reads)
        delivery_standard = @($guidance.delivery_standard)
        topology_version = "18-window-orchestra-v2"
        completed_items_removed = $completedRemoved
        remaining_items = $items.Count
        items = @($items)
        queue_kind = "active-unresolved"
        rebased_utc = $nowUtc
    }

    $queuePath = Join-Path $workflowRoot ("queues/window-{0:D2}.json" -f $windowNumber)
    $queueMdPath = $queuePath -replace "\.json$", ".md"
    Write-JsonFile -Path $queuePath -Payload $queuePayload
    Write-TextFile -Path $queueMdPath -Content (New-QueueMarkdown -WindowEntry $entry -QueuePayload ([pscustomobject]$queuePayload))

    $baseState = if (($windowNumber -le 15) -and $existingStates.ContainsKey($windowNumber)) { $existingStates[$windowNumber] } else { $null }
    $statePayload = New-WorkerState -BaseState $baseState -WindowEntry $entry -RemainingItems $items.Count -Stamp $nowUtc
    Write-JsonFile -Path (Join-Path $workflowRoot $entry.state_file) -Payload $statePayload
}

$compilerBaseMap = @{
    16 = if ($existingStates.ContainsKey(17)) { $existingStates[17] } elseif ($existingStates.ContainsKey(16)) { $existingStates[16] } else { $null }
    17 = if ($existingStates.ContainsKey(18)) { $existingStates[18] } elseif ($existingStates.ContainsKey(17)) { $existingStates[17] } else { $null }
    18 = if ($existingStates.ContainsKey(19)) { $existingStates[19] } elseif ($existingStates.ContainsKey(18)) { $existingStates[18] } else { $null }
}

foreach ($entry in @($windows | Where-Object { $_.kind -in @("precompile", "final") } | Sort-Object window)) {
    $baseState = $compilerBaseMap[[int]$entry.window]
    $statePayload = New-CompilerState -BaseState $baseState -WindowEntry $entry -Stamp $nowUtc
    Write-JsonFile -Path (Join-Path $workflowRoot $entry.state_file) -Payload $statePayload
}

$configPayload = [ordered]@{
    report_file = $reportFile
    windows = @($windows)
}
Write-JsonFile -Path (Join-Path $workflowRoot "config/windows.json") -Payload $configPayload

$migrationReport = [ordered]@{
    migrated_utc = $nowUtc
    topology = [ordered]@{
        worker_windows = @(1..15)
        precompiler_windows = @(16, 17)
        final_window = 18
    }
    runtime_precompiler = [ordered]@{
        window = 16
        upstreams = @(1..7)
    }
    tooling_guardrail_precompiler = [ordered]@{
        window = 17
        upstreams = @(8..15)
    }
    final_compiler = [ordered]@{
        window = 18
        upstreams = @(16, 17)
    }
    worker_backlog = @(
        foreach ($windowNumber in 1..15) {
            $queueSnapshot = Get-Content -Raw (Join-Path $workflowRoot ("queues/window-{0:D2}.json" -f $windowNumber)) | ConvertFrom-Json
            [ordered]@{
                window = $windowNumber
                total_bug_ids = @($fullAssignments[$windowNumber]).Count
                completed_items_removed = [int]$queueSnapshot.completed_items_removed
                remaining_items = @($queueSnapshot.items).Count
            }
        }
    )
}
Write-JsonFile -Path (Join-Path $workflowRoot "TOPOLOGY_MIGRATION_REPORT.json") -Payload $migrationReport

$stalePaths = @(
    (Join-Path $workflowRoot "queues/window-16.json"),
    (Join-Path $workflowRoot "queues/window-16.md"),
    (Join-Path $workflowRoot "state/window-19.json"),
    (Join-Path $workflowRoot "out/window-19")
)
foreach ($stalePath in $stalePaths) {
    if (Test-Path -LiteralPath $stalePath) {
        Remove-Item -LiteralPath $stalePath -Recurse -Force
    }
}

[ordered]@{
    migrated_utc = $nowUtc
    workflow_root = $workflowRoot
    worker_windows = @(1..15)
    precompiler_windows = @(16, 17)
    final_window = 18
} | ConvertTo-Json -Depth 8
