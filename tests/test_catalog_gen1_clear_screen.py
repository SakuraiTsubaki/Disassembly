import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gen1_clear_screen.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen1_clear_screen", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClearScreenCatalogTests(unittest.TestCase):
    def test_decodes_control_structure_and_operands(self):
        code = bytes.fromhex("0168010421a0c33e7f220d20fc0520f9c3d73d")
        data = bytes(0x200) + code + bytes(0x100)
        self.assertEqual(MODULE.locate(data), [{"offset": 0x200,
                                                "tilemap_address": 0xC3A0,
                                                "blank_tile": 0x7F,
                                                "delay3_address": 0x3DD7}])

    def test_rejects_non_ram_tilemap(self):
        code = bytes.fromhex("016801042100803e7f220d20fc0520f9c3d73d")
        self.assertIsNone(MODULE.decode_candidate(code, 0))

    def test_profiles_pin_primary_sources(self):
        self.assertEqual(set(MODULE.PROFILES), {"classic", "yellow"})
        self.assertTrue(all(len(item["commit"]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
