import unittest

from tools import catalog_gen2_disable_lcd as lcd


class DisableLCDCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(lcd.locate(b"\0" * 9 + lcd.ROUTINE), [9])

    def test_rejects_wrong_wait_line(self):
        changed = lcd.ROUTINE.replace(bytes.fromhex("fe91"), bytes.fromhex("fe90"))
        self.assertEqual(lcd.locate(changed), [])

    def test_rejects_missing_ie_restore(self):
        changed = lcd.ROUTINE[:-3] + bytes.fromhex("e00fc9")
        self.assertEqual(lcd.locate(changed), [])


if __name__ == "__main__":
    unittest.main()
