from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disassemble_gba_entry", ROOT / "tools" / "disassemble_gba_entry.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleGbaEntryTests(unittest.TestCase):
    def test_ruby_branch_round_trip(self):
        result = module.analyze(struct.pack("<I", 0xEA000032) + bytes(12))
        self.assertEqual((result["target_address"], result["instruction_bytes_le"]), (0x080000D0, "320000ea"))
        self.assertEqual(module.encode(result["target_address"]), 0xEA000032)
        self.assertTrue(result["round_trip_verified"])

    def test_emerald_branch_round_trip(self):
        result = module.decode(0xEA00007F)
        self.assertEqual(result["target_address"], 0x08000204)
        self.assertEqual(module.encode(result["target_address"]), 0xEA00007F)

    def test_rejects_hash_mismatch_and_non_branch(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            module.analyze(struct.pack("<I", 0xEA000032), "0" * 64)
        with self.assertRaisesRegex(ValueError, "B/BL"):
            module.decode(0xE1A00000)


if __name__ == "__main__":
    unittest.main()
