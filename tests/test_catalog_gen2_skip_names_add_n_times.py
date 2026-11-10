import unittest

from tools import catalog_gen2_skip_names_add_n_times as array


class SkipNamesAddNTimesCatalogToolTests(unittest.TestCase):
    def test_locate_and_immediate(self):
        pair = bytes((0x01, 6, 0)) + array.TAIL + array.TAIL
        found = array.locate(b"\0" * 3 + pair)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name_length"], 6)
        self.assertEqual(found[0]["add_n_times_address"], 3 + array.SKIP_LENGTH)

    def test_add_n_times(self):
        self.assertEqual(array.add_n_times(0x1000, 3, 11), 0x1021)
        self.assertEqual(array.add_n_times(0xFFFF, 1, 1), 0)

    def test_zero_count(self):
        self.assertEqual(array.add_n_times(0x1234, 0, 11), 0x1234)

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            array.add_n_times(0, 256, 1)


if __name__ == "__main__":
    unittest.main()
