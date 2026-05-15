from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from xyzgl.knowledge.lithosphere import Lithosphere


class DnaPersistenceTests(unittest.TestCase):
    def test_lithosphere_persists_and_restores_dna_geometry(self) -> None:
        with TemporaryDirectory() as td:
            litho = Lithosphere(embed_dim=16, grains=4, seed=7, path_prefix=td)
            dna_path = Path(td) / "dna_geometry.bin"

            self.assertTrue(dna_path.exists())
            self.assertFalse(litho.dna_loaded)

            restored = Lithosphere(embed_dim=16, grains=4, seed=123, path_prefix=td)

        self.assertTrue(restored.dna_loaded)
        self.assertTrue(np.array_equal(litho.P, restored.P))
        self.assertTrue(np.array_equal(litho.R, restored.R))

    def test_corrupt_dna_file_recovers_to_valid_shape(self) -> None:
        with TemporaryDirectory() as td:
            dna_path = Path(td) / "dna_geometry.bin"
            dna_path.write_bytes(b"broken")

            litho = Lithosphere(embed_dim=8, grains=2, seed=11, path_prefix=td)

            self.assertFalse(litho.dna_loaded)
            self.assertEqual(dna_path.stat().st_size, ((8 * 2) + (3 * 8)) * 4)
            self.assertEqual(litho.P.shape, (8, 2))
            self.assertEqual(litho.R.shape, (3, 8))

    def test_missing_file_regenerates_and_saves(self) -> None:
        with TemporaryDirectory() as td:
            dna_path = Path(td) / "dna_geometry.bin"
            self.assertFalse(dna_path.exists())

            litho = Lithosphere(embed_dim=8, grains=3, seed=5, path_prefix=td)

            self.assertFalse(litho.dna_loaded)
            self.assertTrue(dna_path.exists())
            self.assertEqual(
                dna_path.stat().st_size,
                ((8 * 3) + (3 * 8)) * np.dtype(np.float32).itemsize,
            )

            reloaded = Lithosphere(embed_dim=8, grains=3, seed=999, path_prefix=td)
            self.assertTrue(reloaded.dna_loaded)
            self.assertTrue(np.array_equal(reloaded.P, litho.P))
            self.assertTrue(np.array_equal(reloaded.R, litho.R))


if __name__ == "__main__":
    unittest.main()
