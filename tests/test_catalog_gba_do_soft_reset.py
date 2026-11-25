import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_do_soft_reset.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_do_soft_reset", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DoSoftResetCatalogTests(unittest.TestCase):
    def test_profiles_and_variants(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertEqual(MODULE.REG_IME, 0x04000208)
        self.assertEqual(MODULE.DMA1_BASE, 0x040000BC)
        self.assertEqual(MODULE.DMA3_BASE, 0x040000D4)

    def test_source_preserves_rtc_difference(self):
        self.assertIn("bl SiiRtcProtect", MODULE.source_text("rs"))
        self.assertIn("#0xFF", MODULE.source_text("emerald").replace(" ", ""))
        self.assertNotIn("SiiRtcProtect", MODULE.source_text("frlg"))
        self.assertIn("#0xDF", MODULE.source_text("frlg").replace(" ", ""))
        self.assertNotIn(".hword", MODULE.source_text("frlg"))


if __name__ == "__main__":
    unittest.main()
