# Active Queue: Window 02

- Name: Grounding and Prompt Assembly
- Area: Owns grounding corpora, prompt assembly, prompt-budget guards, and grounding-path integrity bugs.
- Archived source queue: `queues/window-02.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 6
- Remaining items: 5

1. BUG-19 | original #3 | phase 2 | High | Grounding assembly stops at the first oversized snippet header
   files: xyzgl/grounding/prompting.py
2. BUG-69 | original #7 | phase 2 | High | Oversized grounding manifests silently disable grounding while the audit still passes
   files: tools/grounding_injection_audit.py, xyzgl/grounding/corpus.py
3. BUG-80 | original #8 | phase 2 | High | Whitespace-only blank lines are not treated as paragraph breaks in grounding corpora, so poison and clean context can collapse into one oversized paragraph
   files: xyzgl/grounding/corpus.py
4. BUG-92 | original #10 | phase 2 | High | `manifest.json` source paths using Windows separators silently drop valid grounding sources on POSIX
   files: xyzgl/grounding/corpus.py
5. BUG-102 | original #11 | phase 2 (via Phase 6 audit) | High | `build_tutor_prompt()` silently re-clamps `grounding_max_snippets` to 64, so injected grounding can disagree with both config and direct grounding output
   files: tools/doc_code_link_checker.py, tools/grounding_injection_audit.py, tools/protocol_drift_radar.py, tools/repro_replay_diff.py, tools/repro_session_smoke.py, tools/seed_sweep.py, tools/selfcheck.py, tools/targeted_sweep.py, xyzgl/config.py, xyzgl/prompting.py, xyzgl/protocols.py
