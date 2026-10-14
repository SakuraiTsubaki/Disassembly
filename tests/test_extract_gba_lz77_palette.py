import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_gba_lz77_palette", ROOT / "tools/extract_gba_lz77_palette.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtractGbaLz77PaletteTests(unittest.TestCase):
    def test_literal_palette(self):
        raw = bytes(range(32))
        stream = bytes((0x10, 32, 0, 0, 0)) + raw[:8] + bytes((0,)) + raw[8:16] + bytes((0,)) + raw[16:24] + bytes((0,)) + raw[24:]
        palette, report = MODULE.extract(stream, 0)
        self.assertTrue(palette.startswith(b"JASC-PAL\n0100\n16\n"))
        self.assertEqual(report["decompressed_length"], 32)
        self.assertEqual(report["color_count"], 16)
        self.assertFalse(report["raw_rom_bytes_included"])

    def test_non_palette_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "16-color"):
            MODULE.extract(bytes((0x10, 1, 0, 0, 0, 0)), 0)


if __name__ == "__main__":
    unittest.main()
