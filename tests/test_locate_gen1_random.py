import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("locate_gen1_random", ROOT / "tools/locate_gen1_random.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def routine(add=0xD3, sub=0xD4):
    return bytes((0xF0,0x04,0x47,0xF0,add,0x88,0xE0,add,0xF0,0x04,0x47,0xF0,sub,0x98,0xE0,sub,0xC9))


class LocateGen1RandomTests(unittest.TestCase):
    def test_locates_banked_routine_and_state(self):
        data = bytearray(0xD000)
        data[0xC234:0xC234 + MODULE.LENGTH] = routine()
        match = MODULE.locate(bytes(data))[0]
        self.assertEqual((match["bank"], match["address"]), (3, 0x4234))
        self.assertEqual(match["globals"], {"hRandomAdd": 0xFFD3, "hRandomSub": 0xFFD4})

    def test_rejects_non_adjacent_state_bytes(self):
        self.assertEqual(MODULE.locate(routine(0xD3, 0xD5)), [])


if __name__ == "__main__":
    unittest.main()
