from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disassemble_gb_basic_block", ROOT / "tools" / "disassemble_gb_basic_block.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleGbBasicBlockTests(unittest.TestCase):
    def test_direct_jump_block(self):
        result = module.disassemble(bytes.fromhex("c3da09"), 0)
        self.assertEqual((result["byte_length"], result["instruction_count"], result["terminator"]), (3, 1, "jp $09da"))

    def test_enable_interrupts_before_return(self):
        result = module.disassemble(bytes.fromhex("fbc9"), 0)
        self.assertEqual([item["source"] for item in result["instructions"]], ["ei", "ret"])

    def test_decrement_before_branch(self):
        result = module.disassemble(bytes.fromhex("3d20fd"), 0)
        self.assertEqual(result["terminator"], "jr nz $0000")

    def test_conditional_relative_branch_ends_block(self):
        result = module.disassemble(bytes.fromhex("fe112803"), 0)
        self.assertEqual(result["instructions"][-1]["target_address"], 7)
        self.assertEqual(result["block_bytes"], "fe112803")

    def test_immediate_store_before_branch(self):
        result = module.disassemble(bytes.fromhex("360020fc"), 0)
        self.assertEqual(
            [item["source"] for item in result["instructions"]],
            ["ld [hl], $00", "jr nz $0000"],
        )

    def test_absolute_store_before_branch(self):
        result = module.disassemble(bytes.fromhex("ea00c01800"), 0)
        self.assertEqual(result["instructions"][0]["source"], "ld [$c000], a")
        self.assertEqual(result["terminator"], "jr $0005")

    def test_high_memory_load_before_branch(self):
        result = module.disassemble(bytes.fromhex("f0401800"), 0)
        self.assertEqual(result["instructions"][0]["source"], "ldh a, [$ff00 + $40]")

    def test_register_immediate_before_branch(self):
        result = module.disassemble(bytes.fromhex("26ff1800"), 0)
        self.assertEqual(result["instructions"][0]["source"], "ld h, $ff")

    def test_rgbds_render_preserves_instruction_order(self):
        result = module.disassemble(bytes(0x100) + bytes.fromhex("fe112803"), 0x100)
        source = module.render_rgbds(result)
        self.assertIn('SECTION "Entry Target Block", ROM0[$0100]', source)
        self.assertLess(source.index("cp $11"), source.index("jr z $0107"))

    def test_rgbds_render_accepts_distinct_section_and_label(self):
        result = module.disassemble(bytes.fromhex("c3da09"), 0)
        source = module.render_rgbds(result, "Bootstrap Block", "BootstrapBlock")
        self.assertIn('SECTION "Bootstrap Block", ROM0[$0000]', source)
        self.assertIn("BootstrapBlock::", source)

    def test_unsupported_opcode_and_missing_terminator_fail(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            module.disassemble(bytes.fromhex("ff"), 0)
        with self.assertRaisesRegex(ValueError, "no basic-block"):
            module.disassemble(bytes.fromhex("f3af"), 0)


if __name__ == "__main__":
    unittest.main()
