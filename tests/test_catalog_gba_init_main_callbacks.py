import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_init_main_callbacks.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_init_main_callbacks", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitMainCallbacksCatalogTests(unittest.TestCase):
    def test_profiles_preserve_family_shapes(self):
        self.assertEqual(MODULE.PROFILES["rs"]["shape"], (22, 11, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["emerald"]["shape"], (38, 19, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["frlg"]["shape"], (48, 24, 1, 1, 0))

    def test_instruction_forms(self):
        def cfg(values):
            return {"instructions": [{"address": i * 2, "halfword": value}
                                     for i, value in enumerate(values)]}
        rs = cfg([0xB500, 0x4805, 0x2100, 0x6201, 0x6241, 0x6001,
                  0x4803, 0xF000, 0xF800, 0xBC01, 0x4700])
        self.assertEqual(MODULE.instruction_form(rs), "rs-base")

    def test_primary_sources_are_pinned(self):
        self.assertTrue(all(len(item["commit"]) == 40 for item in MODULE.PROFILES.values()))


if __name__ == "__main__":
    unittest.main()
