import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_check_flash_memory.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_check_flash_memory", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CheckFlashMemoryCatalogTests(unittest.TestCase):
    def test_signature(self):
        cfg = {"start_address": 0, "range_end": 38, "instruction_halfwords": 17,
               "calls": [{}, {}], "returns": [{}], "edges": [{}, {}, {}]}
        self.assertEqual(MODULE.shape(cfg), MODULE.SHAPE)

    def test_profiles_pin_primary_sources(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertTrue(all(len(item[1]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
