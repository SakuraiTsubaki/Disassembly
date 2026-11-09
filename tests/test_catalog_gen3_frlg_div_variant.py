import unittest

from tools import catalog_gen3_frlg_div_variant as div


class FrlgDivVariantToolTests(unittest.TestCase):
    def test_locates_signature(self):
        self.assertEqual(div.locate(b"x" + div.SIGNATURE + b"y"), [1])

    def test_reports_all_matches(self):
        data = div.SIGNATURE + b"x" + div.SIGNATURE
        self.assertEqual(div.locate(data), [0, 5])

    def test_absent_signature(self):
        self.assertEqual(div.locate(b"\0" * 16), [])


if __name__ == "__main__":
    unittest.main()
