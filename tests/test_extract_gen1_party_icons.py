import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("party_icons", ROOT / "tools/extract_gen1_party_icons.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class PartyIconExtractorTests(unittest.TestCase):
    def test_dimensions(self):
        self.assertEqual((len(MODULE.ICON_NAMES), MODULE.FRAMES_PER_ICON, MODULE.LENGTH), (4, 2, 256))
    def test_source_interleave_is_restored(self):
        raw = b"".join(bytes([index]) * MODULE.FRAME_BYTES for index in range(8))
        icons = MODULE.split_icons(raw)
        self.assertEqual(icons["bug"], bytes([0]) * 32 + bytes([2]) * 32)
        self.assertEqual(icons["quadruped"], bytes([5]) * 32 + bytes([7]) * 32)
        atlas = MODULE.atlas_tiles(raw)
        self.assertEqual((len(atlas), atlas[:16], atlas[16:32]), (256, bytes([0]) * 16, bytes([1]) * 16))
        composed = MODULE.composed_atlas_tiles(raw)
        self.assertEqual(len(composed), 512)
    def test_horizontal_tile_flip(self):
        tile = bytes([0b10000001, 0b11110000] * 8)
        flipped = MODULE.flip_tile_horizontally(tile)
        self.assertEqual(flipped[:2], bytes([0b10000001, 0b00001111]))
    def test_language(self):
        self.assertEqual(MODULE.release_language("yellow-fr-rev0"), "French")
    def test_unique_offset(self):
        self.assertEqual(MODULE.unique_offset(b"xxICONSyy", b"ICONS"), 2)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError): MODULE.unique_offset(b"ICONSICONS", b"ICONS")
if __name__ == "__main__": unittest.main()
