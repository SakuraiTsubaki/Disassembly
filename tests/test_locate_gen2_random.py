import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("locate_gen2_random", ROOT / "tools/locate_gen2_random.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def routine(add=0xE1, sub=0xE2):
    return bytes((0xC5,0xF0,0x04,0x47,0xF0,add,0x88,0xE0,add,0xF0,0x04,0x47,0xF0,sub,0x98,0xE0,sub,0xC1,0xC9))


class LocateGen2RandomTests(unittest.TestCase):
    def test_locates_bank_and_hram_state(self):
        data = bytearray(0x9000)
        data[0x8123:0x8123 + MODULE.LENGTH] = routine()
        match = MODULE.locate(bytes(data))[0]
        self.assertEqual((match["bank"], match["address"]), (2, 0x4123))
        self.assertEqual(match["globals"], {"hRandomAdd": 0xFFE1, "hRandomSub": 0xFFE2})

    def test_rejects_non_adjacent_state_bytes(self):
        data = routine(0xE1, 0xE3)
        self.assertEqual(MODULE.locate(data), [])


if __name__ == "__main__":
    unittest.main()
