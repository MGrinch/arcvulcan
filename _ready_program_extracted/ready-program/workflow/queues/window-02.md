# Window 02 Queue
- Queue preflight reads:
  - NORTH_STAR.md
  - xyzgl/grounding/corpus.py
  - xyzgl/prompting.py
  - xyzgl/config.py

- Delivery standard:
  - Never silently drop valid grounding inputs.
  - Keep prompt budget calculations single-sourced.
  - Use tests that prove both corpus parsing and prompt construction stay aligned.

1. BUG-80 | phase 2 | High | Whitespace-only blank lines are not treated as paragraph breaks in grounding corpora, so poison and clean context can collapse into one oversized paragraph
   files: xyzgl/grounding/corpus.py
   mission: Preserve paragraph boundaries so poisoned and clean grounding passages cannot collapse together. Keep the split rules simple and portable so commercial grounding packs behave the same way across authoring pipelines and operating systems.
   acceptance: Whitespace-only separators still split grounding paragraphs. | Oversized merged paragraphs no longer appear from blank-line-only separators.
   nexus: Treat whitespace-only blank lines as structural paragraph breaks. | Keep chunking stable after normalization.

2. BUG-92 | phase 2 | High | `manifest.json` source paths using Windows separators silently drop valid grounding sources on POSIX
   files: xyzgl/grounding/corpus.py
   mission: Make manifest source path normalization portable across Windows and POSIX. Ensure the normalized path contract is deterministic enough for packaged curriculum assets and customer-provided corpora to round-trip cleanly.
   acceptance: Windows-style manifest paths resolve on POSIX. | Grounding source manifests stay intact across platforms.
   nexus: Normalize separators before manifest lookups. | Avoid dropping valid sources because of host-specific slash conventions.

3. BUG-102 | phase 2 (via Phase 6 audit) | High | `build_tutor_prompt()` silently re-clamps `grounding_max_snippets` to 64, so injected grounding can disagree with both config and direct grounding output
   files: tools/doc_code_link_checker.py, tools/grounding_injection_audit.py, tools/protocol_drift_radar.py, tools/repro_replay_diff.py, tools/repro_session_smoke.py, tools/seed_sweep.py, tools/selfcheck.py, tools/targeted_sweep.py, xyzgl/config.py, xyzgl/prompting.py, xyzgl/protocols.py
   mission: Remove the hidden re-clamp so prompt assembly and direct grounding agree on snippet budget. Give operators one trustworthy knob for grounding spend, latency, and answer richness instead of hidden prompt-budget drift.
   acceptance: Prompt assembly respects the configured snippet cap instead of silently forcing 64. | Audit tools that compare prompt vs grounding outputs remain consistent.
   nexus: Use a single authoritative clamp path for grounding_max_snippets. | Audit dependent tools so they all observe the same configured ceiling.

