import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_clear_cry_songs.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_clear_cry_songs", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClearCrySongsCatalogTests(unittest.TestCase):
    def test_fixed_layout_and_mode(self):
        self.assertEqual(MODULE.FUNCTION_LENGTH, 26)
        self.assertEqual(MODULE.HALFWORD_COUNT, 52)
        self.assertEqual(MODULE.BYTE_COUNT, 104)
        self.assertEqual(MODULE.CPU_SET_MODE, 0x01000034)

    def test_profiles_are_pinned(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertTrue(all(len(item["commit"]) == 40
                            for item in MODULE.PROFILES.values()))

    def test_source_is_semantic(self):
        source = MODULE.source_text()
        for token in ("ClearPokemonCrySongs:", "gPokemonCrySongs", "bl CpuSet"):
            self.assertIn(token, source)
        self.assertNotIn(".hword", source)


if __name__ == "__main__":
    unittest.main()
