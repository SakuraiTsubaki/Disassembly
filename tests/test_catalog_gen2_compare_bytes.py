import unittest

from tools import catalog_gen2_compare_bytes as compare


class CompareBytesCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(compare.locate(b"\0" * 3 + compare.ROUTINE), [3])

    def test_equal(self):
        self.assertEqual(compare.compare_bytes(b"abc", b"abc", 3), (True, 3, 3))

    def test_stops_before_advancing_mismatch(self):
        self.assertEqual(compare.compare_bytes(b"abc", b"axc", 3), (False, 1, 1))

    def test_rejects_invalid_count_or_short_input(self):
        with self.assertRaises(ValueError):
            compare.compare_bytes(b"", b"", 0)
        with self.assertRaises(ValueError):
            compare.compare_bytes(b"a", b"a", 2)


if __name__ == "__main__":
    unittest.main()
