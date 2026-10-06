import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).parents[1] / "tools" / "validate_disassembly_manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_disassembly_manifest", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ManifestValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "manifests").mkdir()
        self.output = self.root / "src" / "block.asm"
        self.output.write_text("Block::\n    ret\n", encoding="utf-8")
        self.rom = self.root / "local.gb"
        self.rom.write_bytes(bytes(range(32)))
        self.manifest_path = self.root / "manifests" / "block.json"
        self.manifest = {
            "schema_version": 1,
            "target": {"release": "fixture", "sha256": MODULE.sha256(self.rom)},
            "blocks": [{
                "path": "startup",
                "start": "0x0004",
                "end_exclusive": "0x0008",
                "bytes_sha256": hashlib.sha256(bytes(range(4, 8))).hexdigest(),
            }],
            "outputs": [{"path": "src/block.asm", "sha256": MODULE.sha256(self.output)}],
            "raw_rom_bytes_included": False,
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_validates_outputs_without_rom(self):
        self.write_manifest()
        result = MODULE.validate(self.manifest_path, self.root)
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked_outputs"], 1)
        self.assertFalse(result["rom_verified"])

    def test_validates_rom_and_block_hashes(self):
        self.write_manifest()
        result = MODULE.validate(self.manifest_path, self.root, self.rom)
        self.assertTrue(result["valid"])
        self.assertTrue(result["rom_verified"])
        self.assertEqual(result["checked_blocks"], 1)

    def test_rejects_output_path_escape(self):
        self.manifest["outputs"][0]["path"] = "../block.asm"
        self.write_manifest()
        result = MODULE.validate(self.manifest_path, self.root)
        self.assertFalse(result["valid"])
        self.assertIn("escapes repository root", " ".join(result["errors"]))

    def test_rejects_modified_output(self):
        self.write_manifest()
        self.output.write_text("changed", encoding="utf-8")
        result = MODULE.validate(self.manifest_path, self.root)
        self.assertFalse(result["valid"])
        self.assertIn("output hash mismatch", " ".join(result["errors"]))

    def test_rejects_overlapping_blocks(self):
        self.manifest["blocks"].append({
            "path": "overlap",
            "start": "0x0007",
            "end_exclusive": "0x0009",
            "bytes_sha256": hashlib.sha256(bytes(range(7, 9))).hexdigest(),
        })
        self.write_manifest()
        result = MODULE.validate(self.manifest_path, self.root)
        self.assertFalse(result["valid"])
        self.assertIn("block ranges overlap", " ".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
