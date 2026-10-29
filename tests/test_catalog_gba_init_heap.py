import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_init_heap.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_init_heap", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class InitHeapCatalogTests(unittest.TestCase):
    def test_profiles_and_shape(self):
        self.assertEqual(MODULE.SHAPE, (18, 9, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["emerald"]["calls_after_reset_bgs"], 2)
        self.assertEqual(MODULE.PROFILES["frlg"]["calls_after_reset_bgs"], 1)

    def test_instruction_form(self):
        values = [0xB500, 0x4A04, 0x6010, 0x4A04, 0x6011,
                  0xF000, 0xF800, 0xBC01, 0x4700]
        cfg = {"instructions": [{"address": i * 2, "halfword": value}
                                for i, value in enumerate(values)]}
        self.assertEqual(MODULE.instruction_form(cfg), "record-arena-then-first-block")

if __name__ == "__main__":
    unittest.main()

