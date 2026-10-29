import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_init_map_music.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_init_map_music", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitMapMusicCatalogTests(unittest.TestCase):
    def test_shared_shape(self):
        self.assertEqual(MODULE.SHAPE, (16, 8, 1, 1, 0))
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})

    def test_instruction_form(self):
        cfg = {"instructions": [{"address": i * 2, "halfword": value}
                                for i, value in enumerate(
                                    [0xB500, 0x4903, 0x2000, 0x7008,
                                     0xF000, 0xF800, 0xBC01, 0x4700])]}
        self.assertEqual(MODULE.instruction_form(cfg), "clear-iwram-byte-then-call")

    def test_primary_sources_are_pinned(self):
        self.assertTrue(all(len(item[1]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
