import unittest

from tools import catalog_gen2_get_hp_pal as hp


class GetHPPalCatalogToolTests(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(hp.locate(b"\0" * 3 + hp.ROUTINE), [3])

    def test_boundaries(self):
        self.assertEqual([hp.classify(x) for x in (255, 24, 23, 10, 9, 0)],
                         [0, 0, 1, 1, 2, 2])

    def test_rejects_out_of_range_input(self):
        with self.assertRaises(ValueError):
            hp.classify(256)


if __name__ == "__main__":
    unittest.main()
