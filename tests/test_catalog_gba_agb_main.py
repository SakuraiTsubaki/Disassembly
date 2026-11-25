import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_agb_main.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_agb_main", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgbMainCatalogTests(unittest.TestCase):
    def test_source_contains_structural_variants(self):
        variants = [
            {"id": "origin", "call_names": ["InitKeys", "WaitForVBlank"]},
            {"id": "global-alt", "call_names": ["InitKeys", "ReadKeys"]},
        ]
        source = MODULE.source_text(variants)
        self.assertIn("AgbMain:", source)
        self.assertIn("AgbMain_global_alt:", source)
        self.assertIn("bl WaitForVBlank", source)
        self.assertNotIn(".hword", source)

    def test_target_equivalence(self):
        calls = [{"target": value} for value in (10, 20, 20, 30, 10)]
        self.assertEqual(MODULE.target_equivalence(calls), [0, 1, 1, 2, 0])


if __name__ == "__main__":
    unittest.main()
