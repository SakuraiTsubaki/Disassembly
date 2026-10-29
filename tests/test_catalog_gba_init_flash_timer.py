import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_init_flash_timer.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_init_flash_timer", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitFlashTimerCatalogTests(unittest.TestCase):
    def test_profiles_preserve_operand_and_size_differences(self):
        self.assertEqual(MODULE.PROFILES["rs"]["shape"], (16, 8, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["emerald"]["shape"], (14, 7, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["frlg"]["shape"], (16, 8, 1, 1, 0))
        self.assertEqual(MODULE.PROFILES["rs"]["handler_source"], "gFlashTimerIntrFunc")
        self.assertEqual(MODULE.PROFILES["emerald"]["operand_form"], "slot-address")

    def test_operand_forms(self):
        def cfg(values):
            return {"instructions": [{"address": index * 2, "halfword": value}
                                     for index, value in enumerate(values)]}
        loaded = cfg([0xB500, 0x4803, 0x6801, 0x2002, 0xF000, 0xF800, 0xBC01, 0x4700])
        direct = cfg([0xB500, 0x4903, 0x2002, 0xF000, 0xF800, 0xBC01, 0x4700])
        self.assertEqual(MODULE.operand_form(loaded), "loaded-handler")
        self.assertEqual(MODULE.operand_form(direct), "slot-address")


if __name__ == "__main__":
    unittest.main()
