from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disassemble_gb_entry", ROOT / "tools" / "disassemble_gb_entry.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleGbEntryTests(unittest.TestCase):
    def test_nop_jp_sequence(self):
        result = module.decode(bytes.fromhex("00c35001"))
        self.assertEqual(result["target_address"], 0x0150)
        self.assertEqual(result["instructions"][1]["bytes"], "c35001")

    def test_rejects_wrong_shape_and_hash(self):
        with self.assertRaisesRegex(ValueError, "four bytes"):
            module.decode(bytes(3))
        with self.assertRaisesRegex(ValueError, "NOP"):
            module.decode(bytes(4))
        with self.assertRaisesRegex(ValueError, "mismatch"):
            module.analyze(bytes(0x200), "0" * 64)


if __name__ == "__main__":
    unittest.main()
