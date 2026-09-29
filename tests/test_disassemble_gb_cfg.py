from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("disassemble_gb_cfg", ROOT / "tools" / "disassemble_gb_cfg.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisassembleGbCfgTests(unittest.TestCase):
    def test_conditional_successors_are_depth_bounded(self):
        data = bytes.fromhex("fe112803af18003e01c9")
        result = module.build_cfg(data, 0, 1)
        self.assertEqual([b["start_address"] for b in result["blocks"]], [0, 4, 7])
        self.assertEqual({(e["kind"], e["target"]) for e in result["edges"] if e["source"] == 0}, {("branch", 7), ("fallthrough", 4)})

    def test_zero_depth_only_decodes_root(self):
        result = module.build_cfg(bytes.fromhex("1800c9"), 0, 0)
        self.assertEqual(len(result["blocks"]), 1)
        self.assertEqual(result["edges"][0]["target"], 2)

    def test_internal_loop_target_is_not_duplicated_as_block(self):
        data = bytes.fromhex("3600230b78b120f8c9")
        result = module.build_cfg(data, 0, 1)
        self.assertEqual([b["start_address"] for b in result["blocks"]], [0, 8])
        self.assertIn({"source": 0, "target": 0, "kind": "branch"}, result["edges"])

    def test_rgbds_render_labels_each_decoded_block(self):
        data = bytes.fromhex("fe112803af18003e01c9")
        source = module.render_rgbds(module.build_cfg(data, 0, 1))
        self.assertIn("Block_0000::", source)
        self.assertIn("Block_0004::", source)
        self.assertIn("Block_0007::", source)

    def test_invalid_depth_and_hash_fail(self):
        with self.assertRaisesRegex(ValueError, "depth"):
            module.build_cfg(bytes.fromhex("c9"), 0, -1)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            module.analyze(bytes.fromhex("c9"), 0, "0" * 64, 0)


if __name__ == "__main__":
    unittest.main()
