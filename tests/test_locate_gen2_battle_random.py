import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "locate_gen2_battle_random", ROOT / "tools/locate_gen2_battle_random.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def wrapper(target_bank=0x0F, target_address=0x6C31, temp=0xCFD7, hrombank=0x9F):
    return bytes((
        0xF0, hrombank, 0xF5, 0x3E, target_bank, 0xD7, 0xCD,
        target_address & 0xFF, target_address >> 8, 0xEA,
        temp & 0xFF, temp >> 8, 0xF1, 0xD7, 0xFA,
        temp & 0xFF, temp >> 8, 0xC9,
    ))


class LocateGen2BattleRandomTests(unittest.TestCase):
    def test_extracts_bank_target_and_state(self):
        data = bytearray(0x50000)
        data[0x3071:0x3071 + MODULE.LENGTH] = wrapper()
        match = MODULE.inspect(bytes(data), 0x3071)
        self.assertEqual((match["bank"], match["address"]), (0, 0x3071))
        self.assertEqual(match["target"], {"bank": 0x0F, "address": 0x6C31, "rom_offset": 0x3EC31})
        self.assertEqual(match["temporary_wram"], 0xCFD7)
        self.assertEqual(match["hROMBank"], 0xFF9F)

    def test_rejects_mismatched_temporary(self):
        data = bytearray(wrapper())
        data[15] ^= 1
        self.assertIsNone(MODULE.inspect(bytes(data), 0))

    def test_rejects_unmapped_target(self):
        self.assertIsNone(MODULE.inspect(wrapper(target_address=0x2000), 0))


if __name__ == "__main__":
    unittest.main()
