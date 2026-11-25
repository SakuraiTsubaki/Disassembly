import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_interrupt_init.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_interrupt_init", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InterruptInitCatalogTests(unittest.TestCase):
    def test_profiles_and_function_lengths(self):
        self.assertEqual(set(MODULE.PROFILES), {"rs", "emerald", "frlg"})
        self.assertEqual(len(MODULE.RS_INIT) * 2, 84)
        self.assertEqual(len(MODULE.COMMON_INIT) * 2, 74)
        self.assertEqual(MODULE.RESTORE_RELATIVE, 144)

    def test_setter_offsets_are_distinct(self):
        self.assertEqual(set(MODULE.SETTER_STORES),
                         {"SetVBlankCallback", "SetHBlankCallback",
                          "SetVCountCallback", "SetSerialCallback"})
        self.assertEqual(MODULE.SETTER_RELATIVE["rs"], (124, 136, 148, 160))

    def test_source_preserves_profile_differences(self):
        self.assertIn("0x04000200", MODULE.source_text("rs"))
        self.assertIn("bl EnableInterrupts", MODULE.source_text("frlg"))
        self.assertIn("RestoreSerialTimer3IntrHandlers:", MODULE.source_text("emerald"))
        self.assertNotIn(".hword", MODULE.source_text("emerald"))


if __name__ == "__main__":
    unittest.main()
