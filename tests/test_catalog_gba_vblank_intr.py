import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_vblank_intr.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_vblank_intr", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VBlankIntrCatalogTests(unittest.TestCase):
    def test_profiles(self):
        self.assertEqual({key: value["length"] for key, value in MODULE.PROFILES.items()}, {"rs": 98, "emerald": 164, "frlg": 132})
        self.assertEqual(len(MODULE.PROFILES["rs"]["calls"]), 6)
        self.assertEqual(len(MODULE.PROFILES["emerald"]["calls"]), 9)

    def test_sources_are_profile_specific(self):
        self.assertIn("m4aSoundVSync", MODULE.source_text("rs"))
        self.assertIn("UpdateWirelessStatusIndicatorSprite", MODULE.source_text("emerald"))
        self.assertNotIn(".hword", MODULE.source_text("frlg"))


if __name__ == "__main__":
    unittest.main()
