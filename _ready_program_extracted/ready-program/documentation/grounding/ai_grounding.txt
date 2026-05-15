# Curriculum Grounding (Local) — How It Works

Daedalus supports **local curriculum grounding**: the Tutor receives short, relevant
snippets from a local corpus and can cite them in its answer.

This feature is **opt-in** so harness runs remain deterministic.

---

## Enable grounding

### Environment
```bash
export DAEDALUS_GROUNDING_MODE=local
export DAEDALUS_GROUNDING_DIR=curriculum
```

Optional tuning:
```bash
export DAEDALUS_GROUNDING_MAX_SNIPPETS=6
export DAEDALUS_GROUNDING_MAX_CHARS=3000
```

### CLI flags
```bash
python -m xyzgl.cli --grounding-mode local --grounding-dir curriculum "Explain 2F vs 1F"
```

---

## Corpus format

### `curriculum/manifest.json`
A minimal manifest:

```json
{
  "schema_version": "curriculum_manifest_v1",
  "sources": [
    { "id": "w59_notes", "title": "My W59 notes", "path": "sources/w59.md",
      "tags": ["w59","fillet","inspection"], "license": "my-notes" }
  ]
}
```

### Source files
Place referenced texts under `curriculum/sources/` as `.md` or `.txt`.

**Legal note:** Only add content you have rights to use (public domain,
open-license, or your own notes).

---

## Retrieval algorithm (deterministic)

Implementation:
- `xyzgl/grounding/corpus.py` loads the manifest and chunks text by blank lines.
- `xyzgl/grounding/retrieval.py` uses **lexical token overlap** (Jaccard score).
- Ties are broken deterministically: score desc, source_id asc, passage ordinal asc.

This means the same `(query, corpus)` yields the same selected snippets.

---

## Prompt injection

The Tutor receives grounding blocks like:

```
<<<DAEDALUS_GROUNDING>>>
[src:demo_fitup:0] Demo: Fit-up, tack welds, and common defects
...excerpt...
<<<END_DAEDALUS_GROUNDING>>>
```

Tutor instruction: **prefer grounded claims** and cite `[src:id:ordinal]` when
making Ontario-specific statements.

---

## Where to look for results

Each turn output includes:

- `prompt_meta.grounding_enabled`
- `prompt_meta.grounding.snippets[]`

So you can audit which sources were used.
