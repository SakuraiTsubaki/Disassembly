import importlib.util
import pathlib
import struct
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_display_interrupts.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_display_interrupts", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DisplayInterruptCatalogTests(unittest.TestCase):
    def test_profiles_and_lengths(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertEqual(len(MODULE.COMMON_HBLANK) * 2, 38)
        self.assertEqual(len(MODULE.EMERALD_VCOUNT) * 2, 42)
        self.assertEqual(len(MODULE.FRLG_VCOUNT) * 2, 38)
        self.assertTrue(all(len(item["commit"]) == 40
                            for item in MODULE.PROFILES.values()))

    def test_masked_slots_accept_only_thumb_bl_pairs(self):
        template = MODULE.COMMON_HBLANK
        words = [0xF000 if value is None and index % 2 else
                 0xF800 if value is None else value
                 for index, value in enumerate(template)]
        self.assertTrue(MODULE.matches_template(tuple(words), template))
        words[5] = 0
        self.assertFalse(MODULE.matches_template(tuple(words), template))

    def test_source_is_semantic(self):
        for profile in MODULE.PROFILES:
            source = MODULE.source_text(profile)
            for token in ("HBlankIntr:", "VCountIntr:", "SerialIntr:"):
                self.assertIn(token, source)
            self.assertNotIn(".hword", source)


if __name__ == "__main__":
    unittest.main()
