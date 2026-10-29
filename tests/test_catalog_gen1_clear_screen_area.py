import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gen1_clear_screen_area.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen1_clear_screen_area", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class ClearScreenAreaCatalogTests(unittest.TestCase):
    def test_signature(self):
        code = bytes.fromhex("3e7f111400e5c5220d20fcc1e1190520f4c9")
        self.assertEqual(MODULE.ROUTINE_LENGTH, 18)
        self.assertEqual(MODULE.decode_candidate(code, 0)["blank_tile"], 0x7F)
        image = bytes(0x150) + code
        self.assertEqual(MODULE.locate(image), [MODULE.decode_candidate(image, 0x150)])

    def test_signature_rejects_wrong_stride(self):
        code = bytes.fromhex("3e7f111500e5c5220d20fcc1e1190520f4c9")
        self.assertIsNone(MODULE.decode_candidate(code, 0))

if __name__ == "__main__":
    unittest.main()
