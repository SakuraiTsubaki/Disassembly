import unittest

from tools import catalog_gen2_get_hp_pal as hp
from tools import catalog_gen2_set_hp_pal as set_hp


class SetHPPalCatalogToolTests(unittest.TestCase):
    def test_locate_adjacent_wrapper(self):
        target = 5
        data = bytes((0xCD, target, 0, 0x72, 0xC9)) + hp.ROUTINE
        found = set_hp.locate(data)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["get_hp_pal_target"], target)

    def test_rejects_wrong_target(self):
        data = bytes.fromhex("cd060072c9") + hp.ROUTINE
        self.assertEqual(set_hp.locate(data), [])

    def test_rejects_nonadjacent_wrapper(self):
        data = bytes.fromhex("cd060072c900") + hp.ROUTINE
        self.assertEqual(set_hp.locate(data), [])


if __name__ == "__main__":
    unittest.main()
