import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "locate_gen2_copy_bytes", ROOT / "tools/locate_gen2_copy_bytes.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LocateGen2CopyBytesTests(unittest.TestCase):
    def test_locates_rom0_routine(self):
        data = b"\0" * 0x30D6 + MODULE.ROUTINE
        match = MODULE.locate(data)[0]
        self.assertEqual((match["rom_offset"], match["bank"], match["address"]), (0x30D6, 0, 0x30D6))
        self.assertEqual(match["length"], 14)

    def test_locates_banked_routine(self):
        offset = 0x12345
        data = b"\0" * offset + MODULE.ROUTINE
        match = MODULE.locate(data)[0]
        self.assertEqual((match["bank"], match["address"]), (4, 0x6345))

    def test_requires_exact_split_countdown_shape(self):
        altered = bytearray(MODULE.ROUTINE)
        altered[11] ^= 1
        self.assertEqual(MODULE.locate(bytes(altered)), [])

    def test_finds_multiple_candidates_for_caller_to_reject(self):
        self.assertEqual(len(MODULE.locate(MODULE.ROUTINE * 2)), 2)


if __name__ == "__main__":
    unittest.main()
