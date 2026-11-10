import unittest

from tools import catalog_gen1_is_in_array as array


class Gen1IsInArrayCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(array.locate(b"\0" * 3 + array.ROUTINE), [3])

    def test_stride_and_terminator(self):
        data = bytes((2, 9, 4, 9, 0xff))
        self.assertEqual(array.is_in_array(data, 4, 2), (True, 1))
        self.assertEqual(array.is_in_array(data, 3, 2), (False, 2))
        self.assertEqual(array.is_in_array(bytes((0xff,)), 0xff, 1), (False, 0))

    def test_language_order(self):
        releases = [{"id": x.lower(), "language": x, "revision": 0}
                    for x in ("German", "Japanese", "Spanish", "English")]
        self.assertEqual([x["language"] for x in array.ordered(releases)],
                         ["Japanese", "English", "German", "Spanish"])

    def test_rejects_missing_terminator(self):
        with self.assertRaises(ValueError):
            array.is_in_array(bytes((1, 2)), 3, 1)


if __name__ == "__main__":
    unittest.main()
