from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xyzgl.knowledge.graph import GraphLoadError, KnowledgeGraph, Node, default_graph, load_graph, save_graph


class GraphPersistenceTests(unittest.TestCase):
    def test_save_load_preserves_long_node_ids_without_merging(self) -> None:
        base = "x" * 80
        node_a = Node(
            node_id=base + "A",
            title="Mastered",
            summary="first",
            required_keywords=["alpha"],
            confidence=1.0,
            fragility_flags=[],
        )
        node_b = Node(
            node_id=base + "B",
            title="Unmastered",
            summary="second",
            required_keywords=["beta"],
            confidence=0.0,
            fragility_flags=[],
        )
        graph = KnowledgeGraph(nodes=[node_a, node_b])

        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            save_graph(graph, path)
            persisted = path.read_text(encoding="utf-8")
            loaded = load_graph(path)

        self.assertIn(node_a.node_id, persisted)
        self.assertIn(node_b.node_id, persisted)
        self.assertEqual([n.node_id for n in loaded.nodes], [node_a.node_id, node_b.node_id])
        self.assertEqual([n.required_keywords for n in loaded.nodes], [["alpha"], ["beta"]])
        self.assertEqual([n.confidence for n in loaded.nodes], [1.0, 0.0])

    def test_save_graph_rejects_node_ids_that_change_on_reload(self) -> None:
        graph = KnowledgeGraph(
            nodes=[
                Node(
                    node_id=" padded ",
                    title="bad",
                    summary="",
                    required_keywords=[],
                    confidence=0.0,
                    fragility_flags=[],
                )
            ]
        )

        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            with self.assertRaisesRegex(ValueError, "must not change during persistence"):
                save_graph(graph, path)


    def test_load_graph_missing_file_uses_default_graph(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "missing_graph.json"
            loaded = load_graph(path)

        self.assertEqual([n.node_id for n in loaded.nodes], [n.node_id for n in default_graph().nodes])

    def test_load_graph_invalid_existing_file_raises_instead_of_falling_back(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            path.write_text('{"nodes": [}', encoding="utf-8")

            with self.assertRaisesRegex(GraphLoadError, "invalid graph file"):
                load_graph(path)

    def test_load_graph_duplicate_keys_raise_instead_of_falling_back(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            path.write_text('{"nodes": [], "nodes": []}', encoding="utf-8")

            with self.assertRaisesRegex(GraphLoadError, "invalid graph file"):
                load_graph(path)


    def test_load_graph_rejects_node_ids_that_change_on_reload(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            path.write_text(
                '{"nodes": [{"node_id": " padded ", "title": "bad", "summary": "", "required_keywords": []}]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(GraphLoadError, "must not change on reload"):
                load_graph(path)

    def test_load_graph_rejects_identity_colliding_persisted_rows(self) -> None:
        duplicate_id = "x" * 80
        with TemporaryDirectory() as td:
            path = Path(td) / "knowledge_graph.json"
            path.write_text(
                """{
  "nodes": [
    {"node_id": "%s", "title": "first", "summary": "", "required_keywords": ["alpha"], "confidence": 1.0},
    {"node_id": "%s", "title": "second", "summary": "", "required_keywords": ["beta"], "confidence": 0.0}
  ]
}
""" % (duplicate_id, duplicate_id),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(GraphLoadError, "collides on reload"):
                load_graph(path)


if __name__ == "__main__":
    unittest.main()
