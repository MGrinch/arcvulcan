from __future__ import annotations

import unittest

import numpy as np

from xyzgl.knowledge.lithosphere import Lithosphere


class ProjectionScalingTests(unittest.TestCase):
    def test_projection_scaling_and_meta_are_recorded(self) -> None:
        litho = Lithosphere(embed_dim=4, grains=2, seed=5, projection_scale=3.5)
        vector = [1.0, -0.5, 0.25, 0.75]

        entry = litho.get_or_create("node-1", vector, "demo text")
        expected = np.asarray((litho.R @ litho._coerce_vector(vector)) * 3.5, dtype=np.float32)

        self.assertTrue(np.allclose(entry.projection_3d, expected))
        self.assertEqual(litho.get_meta("node-1"), {"jid": "node-1", "text": "demo text"})

    def test_to_dict_includes_projection_scale_and_meta(self) -> None:
        litho = Lithosphere(embed_dim=4, grains=2, seed=9, projection_scale=2.0)
        litho.get_or_create("node-2", [0.1, 0.2, 0.3, 0.4], "summary")

        snapshot = litho.to_dict()

        self.assertEqual(snapshot["projection_scale"], 2.0)
        self.assertIn("node-2", snapshot["meta"])
        self.assertEqual(snapshot["meta"]["node-2"]["jid"], "node-2")


if __name__ == "__main__":
    unittest.main()
