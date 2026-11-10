import unittest

from tools import catalog_gen2_clear_joypad as clear


class ClearJoypadCatalogToolTests(unittest.TestCase):
    def test_decode(self):
        found = clear.decode(bytes(0x100) + bytes.fromhex("d9afe0a9e0aac9"), 0x100)
        self.assertIsNotNone(found)
        self.assertEqual(found["address"], 0x101)
        self.assertEqual(found["h_joy_pressed_address"], 0xFFA9)
        self.assertEqual(found["h_joy_down_address"], 0xFFAA)

    def test_rejects_missing_reti_anchor(self):
        self.assertIsNone(clear.decode(bytes.fromhex("c9afe0a9e0aac9"), 0))

    def test_rejects_nonconsecutive_hram_targets(self):
        self.assertIsNone(clear.decode(bytes.fromhex("d9afe0a9e0abc9"), 0))


if __name__ == "__main__":
    unittest.main()
