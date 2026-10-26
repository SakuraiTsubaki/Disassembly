import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "locate_gen1_copy_data", ROOT / "tools/locate_gen1_copy_data.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LocateGen1CopyDataTests(unittest.TestCase):
    def test_locates_rom0_routine(self):
        data = b"\0" * 0x123 + MODULE.ROUTINE + b"\0" * 8
        match = MODULE.locate(data)[0]
        self.assertEqual((match["rom_offset"], match["bank"], match["address"]), (0x123, 0, 0x123))
        self.assertEqual(match["length"], 9)

    def test_locates_banked_routine(self):
        offset = 0xF9E60
        data = b"\0" * offset + MODULE.ROUTINE
        match = MODULE.locate(data)[0]
        self.assertEqual((match["bank"], match["address"]), (0x3E, 0x5E60))

    def test_requires_exact_loop_shape(self):
        altered = bytearray(MODULE.ROUTINE)
        altered[-2] ^= 1
        self.assertEqual(MODULE.locate(bytes(altered)), [])

    def test_finds_multiple_candidates_for_caller_to_reject(self):
        self.assertEqual(len(MODULE.locate(MODULE.ROUTINE * 2)), 2)


if __name__ == "__main__":
    unittest.main()
