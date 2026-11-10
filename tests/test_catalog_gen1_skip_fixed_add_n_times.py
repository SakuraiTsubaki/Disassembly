import unittest

from tools import catalog_gen1_skip_fixed_add_n_times as array


class Gen1SkipFixedAddNTimesCatalogToolTests(unittest.TestCase):
    def test_locate_and_immediate(self):
        pair = array.SKIP_PREFIX + bytes((6, 0)) + array.LOOP + array.ADD
        found = array.locate(b"\0" * 3 + pair)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name_length"], 6)
        self.assertEqual(found[0]["add_address"], 3 + array.SKIP_LENGTH)

    def test_add_n_times_and_wrap(self):
        self.assertEqual(array.add_n_times(0x1000, 3, 11), 0x1021)
        self.assertEqual(array.add_n_times(0xffff, 1, 1), 0)

    def test_zero_count(self):
        self.assertEqual(array.add_n_times(0x1234, 0, 6), 0x1234)

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            array.add_n_times(0, 256, 1)


if __name__ == "__main__":
    unittest.main()
