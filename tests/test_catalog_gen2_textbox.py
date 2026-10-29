import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gen2_textbox.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen2_textbox", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Gen2TextboxCatalogTests(unittest.TestCase):
    def standard_image(self):
        offset, border, palette = 0x200, 0x209, 0x23C
        helper = border + MODULE.BORDER_LENGTH
        border_code = (bytes.fromhex("e53e79223ccd") + helper.to_bytes(2, "little")
                       + bytes.fromhex("3c77e111140019e53e7c223e7fcd")
                       + helper.to_bytes(2, "little")
                       + bytes.fromhex("367ce1111400190520ed3e7d223e7acd")
                       + helper.to_bytes(2, "little") + bytes.fromhex("367ec9")
                       + MODULE.PLACE_CHARS)
        palette_code = bytes.fromhex("112d091904040c0c3e07c5e5220d20fce111140019c10520f1c9")
        image = bytearray(0x300)
        image[offset:offset + 9] = bytes.fromhex("c5e5cd0902e1c11833")
        image[border:border + len(border_code)] = border_code
        image[palette:palette + len(palette_code)] = palette_code
        return bytes(image)

    def test_decodes_standard_suite(self):
        match = MODULE.locate_standard(self.standard_image())[0]
        self.assertEqual(match["border"]["tiles"]["blank"], 0x7F)
        self.assertEqual(match["palette"]["attribute_plane_delta"], 0x092D)

    def test_rejects_bad_helper(self):
        image = bytearray(self.standard_image())
        image[0x238] ^= 1
        self.assertEqual(MODULE.locate_standard(bytes(image)), [])

    def test_lengths_cover_separate_entries(self):
        self.assertEqual((MODULE.WRAPPER_LENGTH, MODULE.BORDER_LENGTH,
                          MODULE.PLACE_CHARS_LENGTH, MODULE.PALETTE_LENGTH),
                         (9, 45, 6, 26))


if __name__ == "__main__":
    unittest.main()

