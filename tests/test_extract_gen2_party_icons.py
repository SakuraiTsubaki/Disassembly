import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "party_icons", ROOT / "tools/extract_gen2_party_icons.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PartyIconExtractorTests(unittest.TestCase):
    def test_table_dimensions(self):
        self.assertEqual(len(MODULE.ICON_NAMES), 38)
        self.assertEqual(MODULE.BYTES_PER_ICON, 128)
        self.assertEqual(MODULE.LENGTH, 4864)

    def test_atlas_tile_reordering(self):
        raw = b"".join(bytes([index]) * MODULE.BYTES_PER_ICON for index in range(38))
        atlas = MODULE.atlas_tiles(raw)
        self.assertEqual(len(atlas), 40 * MODULE.BYTES_PER_ICON)
        self.assertEqual(atlas[:32], bytes([0]) * 32)
        self.assertEqual(atlas[32:64], bytes([1]) * 32)
        self.assertEqual(atlas[-32:], bytes(32))

    def test_unique_offset(self):
        self.assertEqual(MODULE.unique_offset(b"xxICONSyy", b"ICONS"), 2)

    def test_non_unique_offset_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_offset(b"ICONSICONS", b"ICONS")


if __name__ == "__main__":
    unittest.main()
