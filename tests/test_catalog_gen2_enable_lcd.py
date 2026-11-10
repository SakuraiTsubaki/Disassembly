import unittest

from tools import catalog_gen2_enable_lcd as lcd


class EnableLCDCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(lcd.locate(b"\0" * 5 + lcd.ROUTINE + b"\0"), [5])

    def test_rejects_clear_bit(self):
        self.assertEqual(lcd.locate(bytes.fromhex("f040cbbfe040c9")), [])

    def test_rejects_different_register(self):
        self.assertEqual(lcd.locate(bytes.fromhex("f041cbffe041c9")), [])


if __name__ == "__main__":
    unittest.main()
