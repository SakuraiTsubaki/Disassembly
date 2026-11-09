import unittest

from tools import catalog_gen1_delay3 as delay3


class Delay3CatalogToolTests(unittest.TestCase):
    def test_locates_targeted_delay3(self):
        data = bytes.fromhex("0e03c33412")
        found = delay3.locate_delay3(data, 0x1234)
        self.assertEqual((len(found), found[0]["frame_count"]), (1, 3))

    def test_rejects_other_target(self):
        data = bytes.fromhex("0e03c33412")
        self.assertEqual(delay3.locate_delay3(data, 0x1235), [])

    def test_locates_preserving_wrapper(self):
        data = bytes.fromhex("c5cd3412c1c9")
        found = delay3.locate_protected_delay3(data, 0x1234)
        self.assertEqual((len(found), found[0]["preserved_register"]), (1, "BC"))


if __name__ == "__main__":
    unittest.main()
