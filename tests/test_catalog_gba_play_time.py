import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_play_time.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_play_time", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlayTimeCatalogTests(unittest.TestCase):
    def test_profiles_and_cluster_layouts(self):
        self.assertEqual(MODULE.PROFILES["rs"]["storage"], "direct")
        self.assertEqual(MODULE.PROFILES["emerald"]["storage"], "pointer")
        self.assertEqual(MODULE.PROFILES["frlg"]["storage"], "pointer")
        self.assertEqual(MODULE.LAYOUTS["direct"]["cluster_length"], 216)
        self.assertEqual(MODULE.LAYOUTS["pointer"]["cluster_length"], 232)
        self.assertEqual(len(MODULE.LAYOUTS["direct"]["functions"]), 5)

    def test_reset_signatures_are_profile_specific(self):
        self.assertEqual(len(MODULE.DIRECT_RESET) * 2, 22)
        self.assertEqual(len(MODULE.POINTER_RESET) * 2, 28)
        self.assertNotEqual(MODULE.DIRECT_RESET, MODULE.POINTER_RESET)

    def test_source_is_semantic(self):
        for storage in MODULE.LAYOUTS:
            source = MODULE.source_text(storage)
            for token in ("PlayTimeCounter_Reset:", "PlayTimeCounter_Update:",
                          "PlayTimeCounter_SetToMax:"):
                self.assertIn(token, source)
            self.assertNotIn(".hword", source)


if __name__ == "__main__":
    unittest.main()
