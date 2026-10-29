import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_default_fonts_pointer.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_default_fonts_pointer", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class DefaultFontsPointerCatalogTests(unittest.TestCase):
    def test_shapes_and_order(self):
        self.assertEqual(MODULE.SHAPE, (12, 6, 1, 1, 0))
        self.assertEqual(MODULE.CALLEE_SHAPE, (6, 3, 0, 1, 0))
        self.assertEqual(MODULE.PROFILES["emerald"]["call_offset_from_init_heap"], -1)
        self.assertEqual(MODULE.PROFILES["frlg"]["call_offset_from_init_heap"], 1)

    def test_instruction_form(self):
        values = [0xB500, 0x4802, 0xF000, 0xF800, 0xBC01, 0x4700]
        cfg = {"instructions": [{"address": i * 2, "halfword": value}
                                for i, value in enumerate(values)]}
        self.assertEqual(MODULE.instruction_form(cfg),
                         "load-default-table-then-set-pointer")

if __name__ == "__main__":
    unittest.main()

