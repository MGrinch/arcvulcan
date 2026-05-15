# Active Queue: Window 03

- Name: Graph, Retrieval Bench, and Curriculum Evidence
- Area: Owns graph persistence, retrieval evidence, retrieval benchmark parity, and curriculum-evidence bugs.
- Archived source queue: `queues/window-03.json`
- Audited UTC: 2026-03-19T16:32:16Z
- Completed items removed: 5
- Remaining items: 5

1. BUG-148 | original #1 | phase 2 | High | `save_graph()` truncates `node_id`, so distinct long node identities can collide and merge on reload
   files: xyzgl/knowledge/graph.py
2. BUG-47 | original #7 | phase 2 | High | 20,000-passage cap can be exhausted by filler sources before target content loads
   files: tools/grounding_injection_audit.py
3. BUG-70 | original #8 | phase 2 | Medium | Hard no-overlap chunk splitting breaks retrieval at passage boundaries
   files: xyzgl/grounding/corpus.py
4. BUG-93 | original #9 | phase 2 | High | Retrieval and evaluation can certify snippets whose shown excerpt omits the actual matching evidence
   files: tools/retrieval_eval_bench.py, xyzgl/grounding/retrieval.py
5. BUG-99 | original #10 | phase 6 | High | `retrieval_eval_bench.py` does not validate benchmark-case field types and can false-pass or crash on malformed rows
   files: tools/retrieval_eval_bench.py
