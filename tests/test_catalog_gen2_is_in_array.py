import unittest

from tools import catalog_gen2_is_in_array as array


class IsInArrayCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(array.locate(b"\0" * 3 + array.ROUTINE), [3])

    def test_stride_search(self):
        self.assertEqual(array.is_in_array(bytes((2, 9, 4, 9, 0xff)), 4, 2), (True, 1))
        self.assertEqual(array.is_in_array(bytes((2, 9, 4, 9, 0xff)), 3, 2), (False, 2))

    def test_terminator_cannot_match(self):
        self.assertEqual(array.is_in_array(bytes((0xff,)), 0xff, 1), (False, 0))

    def test_rejects_missing_terminator_or_bad_stride(self):
        with self.assertRaises(ValueError):
            array.is_in_array(bytes((1, 2)), 3, 1)
        with self.assertRaises(ValueError):
            array.is_in_array(bytes((0xff,)), 1, 0)


if __name__ == "__main__":
    unittest.main()
