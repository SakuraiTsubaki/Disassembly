import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_rse_species_sprites.py"
SPEC = importlib.util.spec_from_file_location("catalog_rse_species_sprites", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RseSpeciesSpriteCatalogTests(unittest.TestCase):
    def test_release_prefix_preserves_debug_identity(self):
        release = {"id": "axv-d-rev0-debug", "revision": 0, "build_kind": "debug"}
        self.assertEqual(MODULE.release_prefix("Ruby", release), ("ruby-de-rev0-debug", "de"))

    def test_table_deltas_are_distinct(self):
        self.assertEqual(MODULE.FRONT_TO_BACK, 0x14A0)
        self.assertEqual(MODULE.BACK_TO_PALETTE, 0x0DC0)


if __name__ == "__main__":
    unittest.main()
