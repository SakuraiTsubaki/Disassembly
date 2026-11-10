import unittest

from tools import catalog_gen2_clear_hide_sprites as sprites


class SpriteCatalogToolTests(unittest.TestCase):
    def test_decode_pair(self):
        code = bytes.fromhex("2100c006a0af220520fcc92100c011040006283ea077190520fbc9")
        found = sprites.decode(code, 0)
        self.assertIsNotNone(found)
        self.assertEqual(found["ClearSprites"]["w_shadow_oam_address"], 0xC000)
        self.assertEqual(found["HideSprites"]["address"], 11)
        self.assertEqual(found["HideSprites"]["object_count"], 40)

    def test_rejects_different_shadow_oam_bases(self):
        code = bytes.fromhex("2100c006a0af220520fcc92101c011040006283ea077190520fbc9")
        self.assertIsNone(sprites.decode(code, 0))

    def test_rejects_wrong_hidden_y(self):
        code = bytes.fromhex("2100c006a0af220520fcc92100c011040006283e9f77190520fbc9")
        self.assertIsNone(sprites.decode(code, 0))


if __name__ == "__main__":
    unittest.main()
