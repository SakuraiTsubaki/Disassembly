import unittest

from tools import catalog_gen2_count_set_bits as bits


class CountSetBitsCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        routine = bits.PREFIX + bytes.fromhex("34c2") + bits.SUFFIX
        found = bits.locate(b"\0" * 3 + routine)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["work_ram_address"], 0xC234)

    def test_count(self):
        self.assertEqual(bits.count_set_bits(bytes((0x00, 0x55, 0xFF))), 12)

    def test_rejects_empty_or_too_long_input(self):
        with self.assertRaises(ValueError):
            bits.count_set_bits(b"")
        with self.assertRaises(ValueError):
            bits.count_set_bits(b"\0" * 256)

    def test_rom0_only(self):
        routine = bits.PREFIX + bytes.fromhex("34c2") + bits.SUFFIX
        self.assertEqual(bits.locate(b"\0" * 0x4000 + routine), [])


if __name__ == "__main__":
    unittest.main()
