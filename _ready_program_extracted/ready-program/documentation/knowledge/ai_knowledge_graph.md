# ai_knowledge_graph

The knowledge graph is the minimal state the system uses to decide **what to teach next**.

v0 implementation goals:
- deterministic node selection
- short node summaries (LLM-friendly)
- explicit `required_keywords` for auditable closure

Code surfaces:
- `xyzgl/knowledge/graph.py` — `KnowledgeGraph`, IO, `default_graph()`
- `xyzgl/knowledge/heuristics.py` — `select_next_node(...)`
- `xyzgl/knowledge/update.py` — `close_node(...)`

## File format

`knowledge_graph.json`:

- `schema_version`: `knowledge_graph@1`
- `nodes[]`: list of nodes (id/title/summary/required_keywords/confidence/...)

## Why required_keywords?

In early iterations, closure is decided deterministically by whether the learner answer mentions required keywords.

This keeps harness runs stable and makes the policy auditable. In later iterations, the Tutor can propose closure, but the system should still keep a deterministic safety backstop.
