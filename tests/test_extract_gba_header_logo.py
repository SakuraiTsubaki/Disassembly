from __future__ import annotations

import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extract_gba_header_logo", ROOT / "tools" / "extract_gba_header_logo.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExtractGbaHeaderLogoTests(unittest.TestCase):
    def test_png_shape_and_determinism(self):
        logo = bytes(156)
        decoded = bytes(range(208))
        with mock.patch.object(module, "decode_logo", return_value=decoded):
            png = module.render_logo(logo)
            repeated = module.render_logo(logo)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (416, 64))
        self.assertEqual(png, repeated)

    def test_extract_hash_gate_and_provenance(self):
        logo = bytes(156)
        data = bytes(4) + logo
        digest = hashlib.sha256(data).hexdigest()
        with mock.patch.object(module, "decode_logo", return_value=bytes(208)):
            png, report = module.extract(data, digest)
        self.assertEqual(report["source_bytes_sha256"], hashlib.sha256(data[4:160]).hexdigest())
        self.assertEqual(report["png_sha256"], hashlib.sha256(png).hexdigest())
        with self.assertRaisesRegex(ValueError, "mismatch"):
            module.extract(data, "0" * 64)

    def test_rejects_wrong_logo_size(self):
        with self.assertRaisesRegex(ValueError, "156"):
            module.render_logo(bytes(155))

    def test_cumulative_decoder(self):
        header = ((208 << 8) | 0x82).to_bytes(4, "little")
        deltas = (1).to_bytes(2, "little") * 104
        decoded = module.cumulative_decode(header + deltas)
        self.assertEqual(decoded[:6], b"\x01\x00\x02\x00\x03\x00")
        self.assertEqual(decoded[-2:], b"h\x00")


if __name__ == "__main__":
    unittest.main()
