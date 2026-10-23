import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_logo", ROOT / "tools/catalog_gba_header_logo.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class HeaderLogoCatalogTests(unittest.TestCase):
    def test_expected_hashes(self):
        self.assertEqual(len(MODULE.EXPECTED_LOGO_SHA256), 64)
        self.assertEqual(len(MODULE.EXPECTED_PNG_SHA256), 64)
    def test_release_report_is_publication_safe(self):
        extracted = {"source_offset":4,"source_length":156,"source_bytes_sha256":MODULE.EXPECTED_LOGO_SHA256,"format":"test","width":104,"height":16,"png_sha256":MODULE.EXPECTED_PNG_SHA256,"png_width":416,"png_height":64,"nearest_neighbor_scale":4}
        release = {"id":"bpe-j-rev0-retail","language":"Japanese","revision":0,"build_kind":"retail","sha256":"a"*64}
        report = MODULE.release_report(extracted, release, True, Path("graphics/header/nintendo-logo-jp.png"))
        self.assertTrue(report["origin_reference"])
        self.assertFalse(report["raw_rom_bytes_included"])
        self.assertEqual(report["asset"]["source_length"], 156)
if __name__ == "__main__": unittest.main()
