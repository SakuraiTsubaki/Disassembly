import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gen2_clear_screen.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen2_clear_screen", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Gen2ClearScreenCatalogTests(unittest.TestCase):
    def test_decodes_pair_and_dependencies(self):
        byte_fill = 0x3108
        code = bytes.fromhex("2100c43e7f016801cd0831f040cb7fc8c33412"
                             "3e072168c5016801cd083118e0")
        data = bytes(0x200) + code + bytes(0x40)
        self.assertEqual(MODULE.locate(data, byte_fill), [{
            "offset": 0x200, "variant": "global-inline-wait", "pair_length": 32,
            "clear_tilemap_length": 19, "clear_screen_length": 13,
            "tilemap_address": 0xC400, "blank_tile": 0x7F,
            "wait_bg_map_address": 0x1234, "palette_value": 7,
            "attrmap_address": 0xC568, "clear_screen_offset": 0x213}])

    def test_decodes_korean_split_wait_variant(self):
        byte_fill = 0x31F4
        code = bytes.fromhex("21a0c33e7f016801cdf431f040cb7fc9"
                             "3e0721e0cc016801cdf431cdf00ec8c3c434")
        data = bytes(0xEF0) + code + bytes(0x20)
        self.assertEqual(MODULE.locate(data, byte_fill), [{
            "offset": 0xEF0, "variant": "korean-split-wait", "pair_length": 34,
            "clear_tilemap_length": 16, "clear_screen_length": 18,
            "tilemap_address": 0xC3A0, "blank_tile": 0x7F,
            "wait_bg_map_address": 0x34C4, "palette_value": 7,
            "attrmap_address": 0xCCE0, "clear_screen_offset": 0xF00}])

    def test_rejects_wrong_byte_fill_target(self):
        code = bytes.fromhex("2100c43e7f016801cd0831f040cb7fc8c33412"
                             "3e072168c5016801cd083118e0")
        self.assertIsNone(MODULE.decode_candidate(code, 0, 0x9999))

    def test_profiles_pin_primary_sources(self):
        self.assertEqual(set(MODULE.PROFILES), {"gold-silver", "crystal"})
        self.assertTrue(all(len(item["commit"]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
