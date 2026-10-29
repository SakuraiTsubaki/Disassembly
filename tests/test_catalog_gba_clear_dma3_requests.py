import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_clear_dma3_requests.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_clear_dma3_requests", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClearDma3RequestsCatalogTests(unittest.TestCase):
    def test_shared_shape_and_form(self):
        self.assertEqual(MODULE.SHAPE, (42, 21, 0, 1, 2))
        cfg = {"instructions": [{"address": i * 2, "halfword": value}
                                for i, value in enumerate(MODULE.FORM)]}
        self.assertEqual(MODULE.instruction_form(cfg),
                         "lock-clear-128-requests-unlock")

    def test_primary_sources_are_pinned(self):
        self.assertEqual(set(MODULE.PROFILES), {"emerald", "frlg"})
        self.assertTrue(all(len(item[1]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()

