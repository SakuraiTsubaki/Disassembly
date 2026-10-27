import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "catalog_gba_entry_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_entry_bootstrap", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_sources_use_mnemonics_not_encoded_words(self):
        for source in (MODULE.entry_source(), MODULE.bootstrap_source()):
            self.assertNotIn(".word", source)
        self.assertIn("b rom_bootstrap", MODULE.entry_source())
        self.assertIn("bx r1", MODULE.bootstrap_source())

    def test_edge_kind_counts_are_sorted(self):
        edges = [{"kind": "branch"}, {"kind": "conditional-taken"},
                 {"kind": "branch"}]
        self.assertEqual(
            MODULE.edge_kinds(edges),
            {"branch": 2, "conditional-taken": 1},
        )


if __name__ == "__main__":
    unittest.main()
