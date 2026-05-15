import unittest

from xyzgl.knowledge.graph import KnowledgeGraph, Node
from xyzgl.knowledge.update import close_node, update_mastery_from_resonance


class GradualMasteryTests(unittest.TestCase):
    def _graph(self, *, confidence: float = 0.0, last_verified_turn: int = -1) -> KnowledgeGraph:
        return KnowledgeGraph(
            nodes=[
                Node(
                    node_id="node-a",
                    title="Node A",
                    summary="demo",
                    required_keywords=["demo"],
                    confidence=confidence,
                    fragility_flags=[],
                    last_verified_turn=last_verified_turn,
                )
            ]
        )

    def test_high_resonance_gradually_increments_confidence(self) -> None:
        graph = self._graph(confidence=0.2, last_verified_turn=1)

        updated = update_mastery_from_resonance(
            graph,
            "node-a",
            resonance=0.91,
            text_similarity=0.10,
            turn_index=5,
        )

        node = updated.get("node-a")
        assert node is not None
        self.assertAlmostEqual(node.confidence, 0.3)
        self.assertEqual(node.last_verified_turn, 5)

    def test_threshold_gating_blocks_increment_but_still_tracks_turn(self) -> None:
        graph = self._graph(confidence=0.2, last_verified_turn=3)

        updated = update_mastery_from_resonance(
            graph,
            "node-a",
            resonance=0.9,
            text_similarity=0.95,
            turn_index=6,
        )

        node = updated.get("node-a")
        assert node is not None
        self.assertAlmostEqual(node.confidence, 0.2)
        self.assertEqual(node.last_verified_turn, 6)

    def test_high_similarity_also_triggers_increment(self) -> None:
        graph = self._graph(confidence=0.4, last_verified_turn=0)

        updated = update_mastery_from_resonance(
            graph,
            "node-a",
            resonance=0.1,
            text_similarity=0.96,
            turn_index=4,
        )

        node = updated.get("node-a")
        assert node is not None
        self.assertAlmostEqual(node.confidence, 0.5)
        self.assertEqual(node.last_verified_turn, 4)

    def test_gradual_mastery_caps_confidence_at_one(self) -> None:
        graph = self._graph(confidence=0.95, last_verified_turn=2)

        updated = update_mastery_from_resonance(
            graph,
            "node-a",
            resonance=0.99,
            text_similarity=0.1,
            turn_index=7,
        )

        node = updated.get("node-a")
        assert node is not None
        self.assertEqual(node.confidence, 1.0)
        self.assertEqual(node.last_verified_turn, 7)

    def test_close_node_uses_resonance_confidence_override(self) -> None:
        graph = self._graph(confidence=0.2, last_verified_turn=1)

        updated = close_node(
            graph,
            "node-a",
            turn_index=8,
            confidence_bump=0.25,
            resonance_confidence=0.4,
        )

        node = updated.get("node-a")
        assert node is not None
        self.assertAlmostEqual(node.confidence, 0.6)
        self.assertEqual(node.last_verified_turn, 8)

    def test_close_node_keeps_existing_behavior_without_override(self) -> None:
        graph = self._graph(confidence=0.2, last_verified_turn=1)

        updated = close_node(graph, "node-a", turn_index=9)

        node = updated.get("node-a")
        assert node is not None
        self.assertAlmostEqual(node.confidence, 0.45)
        self.assertEqual(node.last_verified_turn, 9)


if __name__ == "__main__":
    unittest.main()
