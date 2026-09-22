from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extract_gb_header_logo", ROOT / "tools" / "extract_gb_header_logo.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExtractGbHeaderLogoTests(unittest.TestCase):
    def test_png_is_deterministic_scaled_rgba(self):
        png = module.render_logo(bytes(range(48)))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (384, 64))
        self.assertEqual(png, module.render_logo(bytes(range(48))))

    def test_tile_order_changes_at_two_byte_boundary(self):
        first = bytearray(48)
        first[0] = 0x80
        second = bytearray(48)
        second[2] = 0x80
        self.assertNotEqual(module.render_logo(bytes(first)), module.render_logo(bytes(second)))

    def test_extract_records_provenance(self):
        data = bytearray(0x200)
        data[0x104:0x134] = bytes(range(48))
        png, report = module.extract(bytes(data))
        self.assertEqual((report["source_offset"], report["source_length"]), (0x104, 48))
        self.assertEqual((report["width"], report["height"], report["nearest_neighbor_scale"]), (48, 8, 8))
        self.assertEqual(report["png_sha256"], __import__("hashlib").sha256(png).hexdigest())

    def test_hash_gate_and_short_input(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            module.extract(bytes(0x200), "0" * 64)
        with self.assertRaisesRegex(ValueError, "too short"):
            module.extract(bytes(0x120))


if __name__ == "__main__":
    unittest.main()
