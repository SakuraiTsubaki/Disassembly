from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disassemble_gba_bootstrap", ROOT / "tools" / "disassemble_gba_bootstrap.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleGbaBootstrapTests(unittest.TestCase):
    def test_literal_backed_thumb_transition(self):
        data = bytearray(0x40)
        struct.pack_into("<I", data, 0, 0xE59F1000)
        struct.pack_into("<I", data, 4, 0xE12FFF11)
        struct.pack_into("<I", data, 8, 0x08000021)
        result = module.trace(bytes(data), 0)
        self.assertEqual(result["instruction_count"], 2)
        self.assertEqual(result["instructions"][0]["bytes_le"], "00109fe5")
        self.assertEqual((result["transition"]["target_address"], result["transition"]["target_state"]), (0x08000020, "thumb"))

    def test_missing_transition_and_alignment_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "word-aligned"):
            module.trace(bytes(16), 2)
        with self.assertRaisesRegex(ValueError, "no literal-backed"):
            module.trace(bytes(16), 0, 2)


if __name__ == "__main__":
    unittest.main()
