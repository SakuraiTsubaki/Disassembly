from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disassemble_thumb_cfg", ROOT / "tools" / "disassemble_thumb_cfg.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleThumbCfgTests(unittest.TestCase):
    def test_publication_report_omits_raw_halfwords(self):
        result = module.trace(bytes.fromhex("7047"), 0, 2)
        public = module.omit_raw_bytes(result)
        self.assertEqual(public["canonical_instruction_bytes_sha256"], result["canonical_instruction_bytes_sha256"])
        self.assertNotIn("halfword", public["instructions"][0])
        self.assertNotIn("bytes_le", public["instructions"][0])

    def pack(self, *values: int) -> bytes:
        return struct.pack("<" + "H" * len(values), *values)

    def test_conditional_paths_and_bytes(self):
        result = module.trace(self.pack(0xD001, 0x2000, 0xBD00, 0x4770), 0)
        self.assertEqual(len(result["returns"]), 2)
        self.assertEqual(result["instructions"][0]["bytes_le"], "01d0")
        self.assertEqual({edge["kind"] for edge in result["edges"]}, {"conditional-taken", "conditional-fallthrough"})

    def test_bl_is_recorded_without_following_callee(self):
        result = module.trace(self.pack(0xF000, 0xF800, 0x4770), 0)
        self.assertEqual(result["calls"], [{"source": 0x08000000, "target": 0x08000004}])
        self.assertEqual(result["instruction_halfwords"], 3)

    def test_nonreturning_path_is_recorded(self):
        result = module.trace(self.pack(0xE7FE), 0, 2)
        self.assertFalse(result["return_observed"])
        self.assertEqual(result["instruction_halfwords"], 1)


if __name__ == "__main__":
    unittest.main()
