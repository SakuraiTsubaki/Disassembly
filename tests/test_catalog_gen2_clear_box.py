import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gen2_clear_box.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen2_clear_box", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Gen2ClearBoxCatalogTests(unittest.TestCase):
    def test_gold_silver_signature(self):
        image = bytes(0x150) + MODULE.GS_SIGNATURE
        matches = MODULE.locate_standard(image, "gold-silver")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["variant"], "gold-silver-inline")
        self.assertEqual(matches[0]["row_stride"], 20)

    def test_crystal_fallthrough_signature(self):
        image = bytes(0x200) + MODULE.CRYSTAL_SIGNATURE
        match = MODULE.locate_standard(image, "crystal")[0]
        self.assertEqual(match["variant"], "crystal-fallthrough")
        self.assertEqual(match["fill_entry_offset"], 0x202)

    def test_korean_wrapper_resolves_and_validates_core(self):
        core_offset = 0x1FC08D
        image = bytearray(core_offset + MODULE.KOREAN_CORE_LENGTH)
        image[0x300:0x317] = bytes.fromhex(
            "3be5f5e5f806367f2b36402b368de1f1cd732e333333c9")
        image[core_offset:core_offset + MODULE.KOREAN_CORE_LENGTH] = (
            MODULE.KOREAN_PREFIX + MODULE.GS_SIGNATURE)
        matches = MODULE.locate_korean(bytes(image))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["target_offset"], core_offset)
        self.assertEqual(matches[0]["target_bank"], 0x7F)
        self.assertEqual(matches[0]["target_address"], 0x408D)
        core = MODULE.decode_korean_core(bytes(image), core_offset)
        self.assertEqual(core["attribute_plane_delta"], 0x0940)
        self.assertEqual(core["attribute_bit_cleared"], 3)

    def test_korean_wrapper_rejects_unverified_target(self):
        wrapper = bytes.fromhex("3be5f5e5f806367f2b36402b368de1f1cd732e333333c9")
        image = bytes(0x300) + wrapper
        self.assertEqual(MODULE.locate_korean(image), [])

    def test_history_reference_is_pinned(self):
        self.assertEqual(len(MODULE.KOREAN_HISTORY["commit"]), 40)
        self.assertEqual(MODULE.KOREAN_HISTORY["symbol"], "ClearBox")


if __name__ == "__main__":
    unittest.main()

