# Curriculum Corpus Linter

**Goal:** catch corpus/manifest issues before they silently break grounding.

## What it checks
- `curriculum/manifest.json` exists, parses, and has a non-empty `sources` list.
- Each source has a unique `id` and a valid `path`.
- Source files exist and are valid UTF-8.
- Detects duplicate content via SHA-256 fingerprints.

## Usage
```bash
python tools/curriculum_corpus_linter.py --issue ISSUE-YYYYMMDD-NNN
```

## Outputs
- `runs/<run_id>/corpus_lint_report.json`
- `runs/<run_id>/corpus_lint_summary.md`
- `runs/<run_id>/run.json`

## Exit codes
- 0 PASS
- 1 FAIL