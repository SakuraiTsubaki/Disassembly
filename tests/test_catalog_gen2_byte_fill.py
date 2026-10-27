import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "catalog_gen2_byte_fill.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen2_byte_fill", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_locator(self):
        data = b"prefix" + MODULE.ROUTINE + b"suffix"
        self.assertEqual(MODULE.locate(data), [6])

    def test_source_uses_mnemonics(self):
        source = MODULE.source_text()
        self.assertIn("ByteFill::", source)
        self.assertIn("ld [hli], a", source)
        self.assertNotIn("db ", source.lower())


if __name__ == "__main__":
    unittest.main()
