import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "catalog_gba_repeated_callback_cfg.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_repeated_callback_cfg", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_unique_repeated_target(self):
        calls = [
            {"target": 1}, {"target": 2}, {"target": 1},
            {"target": 3}, {"target": 1},
        ]
        self.assertEqual(MODULE.unique_repeated_target(calls), 1)

    def test_rejects_ambiguous_repeated_targets(self):
        calls = [{"target": 1}] * 3 + [{"target": 2}] * 3
        with self.assertRaises(ValueError):
            MODULE.unique_repeated_target(calls)

    def test_edge_kind_counts_are_sorted(self):
        edges = [{"kind": "z"}, {"kind": "a"}, {"kind": "z"}]
        self.assertEqual(MODULE.edge_kinds(edges), {"a": 1, "z": 2})


if __name__ == "__main__":
    unittest.main()
