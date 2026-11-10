import unittest

from tools import catalog_gen2_get_weekday as weekday


class GetWeekdayCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        routine = bytes((weekday.OPCODE, 0x34, 0xC2)) + weekday.TAIL
        found = weekday.locate(b"\0" * 4 + routine)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["cur_day_address"], 0xC234)

    def test_modulo_boundaries(self):
        self.assertEqual([weekday.weekday(x) for x in (0, 6, 7, 13, 14, 255)],
                         [0, 6, 0, 6, 0, 3])

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            weekday.weekday(-1)
        with self.assertRaises(ValueError):
            weekday.weekday(256)

    def test_rom0_only(self):
        routine = bytes((weekday.OPCODE, 0x34, 0xC2)) + weekday.TAIL
        self.assertEqual(weekday.locate(b"\0" * 0x4000 + routine), [])


if __name__ == "__main__":
    unittest.main()
