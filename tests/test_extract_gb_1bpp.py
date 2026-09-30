import importlib.util
import struct
import unittest
from pathlib import Path


PATH = Path(__file__).parents[1] / "tools" / "extract_gb_1bpp.py"
SPEC = importlib.util.spec_from_file_location("extract_gb_1bpp", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtractGb1bppTests(unittest.TestCase):
    def test_render_shape_and_determinism(self):
        raw = bytes([0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81])
        png = MODULE.render(raw, 1)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (32, 32))
        self.assertEqual(png, MODULE.render(raw, 1))

    def test_extract_records_range_without_raw_bytes(self):
        rom = bytes(range(64))
        png, report = MODULE.extract(rom, 8, 2, 2)
        self.assertEqual((report["source_offset"], report["source_length"]), (8, 16))
        self.assertNotIn("source_bytes", report)
        self.assertEqual(report["logical_width"], 16)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_rejects_bad_layout(self):
        with self.assertRaises(ValueError):
            MODULE.render(bytes(24), 2)


if __name__ == "__main__":
    unittest.main()
