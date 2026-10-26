import importlib.util
import struct
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_jasc_palette_catalog", ROOT / "tools/render_jasc_palette_catalog.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def decode_first_scanline(png):
    position = 8
    compressed = bytearray()
    while position < len(png):
        size = struct.unpack(">I", png[position:position + 4])[0]
        kind = png[position + 4:position + 8]
        payload = png[position + 8:position + 8 + size]
        if kind == b"IDAT":
            compressed.extend(payload)
        position += 12 + size
    return zlib.decompress(bytes(compressed)).splitlines()[0]


class RenderJascPaletteCatalogTests(unittest.TestCase):
    def test_parse_and_render(self):
        colors = MODULE.parse_jasc(b"JASC-PAL\n0100\n2\n1 2 3\n250 251 252\n")
        png, width, height = MODULE.render(colors, cell_size=2)
        self.assertEqual((colors, width, height), ([(1, 2, 3), (250, 251, 252)], 4, 2))
        self.assertEqual(struct.unpack(">II", png[16:24]), (4, 2))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_invalid_count_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.parse_jasc(b"JASC-PAL\n0100\n2\n1 2 3\n")

    def test_trailing_blank_line_is_ignored(self):
        self.assertEqual(MODULE.parse_jasc(b"JASC-PAL\n0100\n1\n1 2 3\n\n"), [(1, 2, 3)])

    def test_language_priority(self):
        self.assertEqual(MODULE.palette_language(Path("asset-jp.pal")), "Japanese")
        self.assertEqual(MODULE.palette_language(Path("asset-en.pal")), "English")
        self.assertEqual(MODULE.palette_language(Path("origin.pal")), "Japanese")


if __name__ == "__main__":
    unittest.main()
