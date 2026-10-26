import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_public_graphics", ROOT / "tools/catalog_public_graphics.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def minimal_png(width=2, height=3):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0) + bytes(4)


class PublicGraphicsCatalogTests(unittest.TestCase):
    def test_png_metadata(self):
        self.assertEqual(
            MODULE.png_metadata(minimal_png()),
            {"width": 2, "height": 3, "bit_depth": 8, "color_type": "truecolor", "interlaced": False},
        )

    def test_invalid_png_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.png_metadata(b"not png")

    def test_language_detection(self):
        self.assertEqual(MODULE.asset_language(Path("font-jp.png")), "Japanese")
        self.assertEqual(MODULE.asset_language(Path("font-ko.png")), "Korean")
        self.assertEqual(MODULE.asset_language(Path("font-en.png")), "English")
        self.assertEqual(MODULE.asset_language(Path("top-global.png")), "Global")
        self.assertEqual(MODULE.asset_language(Path("atlas.png")), "Unspecified")


if __name__ == "__main__":
    unittest.main()
