import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_reset_bgs.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_reset_bgs", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ResetBgsCatalogTests(unittest.TestCase):
    def test_shape_and_profiles(self):
        self.assertEqual(MODULE.SHAPE, (20, 10, 2, 1, 0))
        self.assertEqual(set(MODULE.PROFILES), {"emerald", "frlg"})

    def test_instruction_form(self):
        values = [0xB500, 0xF000, 0xF800, 0x4903, 0x2000,
                  0x8208, 0xF000, 0xF800, 0xBC01, 0x4700]
        cfg = {"instructions": [{"address": i * 2, "halfword": value}
                                for i, value in enumerate(values)]}
        self.assertEqual(MODULE.instruction_form(cfg),
                         "reset-structs-clear-dispcnt-hide-bgs")

if __name__ == "__main__":
    unittest.main()

