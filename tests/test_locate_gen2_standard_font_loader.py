import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "locate_gen2_standard_font_loader",
    ROOT / "tools/locate_gen2_standard_font_loader.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Gen2StandardFontLoaderTests(unittest.TestCase):
    def test_gold_loader_and_optional_initializer(self):
        data = bytearray(0x100)
        data[0x20:0x30] = bytes.fromhex("cd341211f24221008801803ec37856")
        match = MODULE.locate_gold_silver(bytes(data))[0]
        self.assertEqual(match["loader_offset"], 0x20)
        self.assertEqual(match["range_end_exclusive"], 0x30)
        self.assertEqual(match["font"]["source_offset"], 0xF82F2)
        self.assertEqual(match["initializer_call"]["target"], 0x1234)
        self.assertEqual(match["transfer"]["target"], 0x5678)

    def test_crystal_four_chunk_loader(self):
        data = bytearray(0x200)
        start = 0x20
        data[start : start + 16] = bytes.fromhex(
            "11004221008801803ef040cb7fca3412"
        )
        for index in range(4):
            chunk = start + 16 + index * 12
            source = 0x4200 + index * 0x100
            destination = 0x8800 + index * 0x200
            data[chunk : chunk + 12] = (
                bytes((0x11, source & 0xFF, source >> 8))
                + bytes((0x21, destination & 0xFF, destination >> 8))
                + bytes((0x01, 32, 0x3E, 0xCD, 0x78, 0x56))
            )
        data[start + 64] = 0xC9
        match = MODULE.locate_crystal(bytes(data))[0]
        self.assertEqual(match["code_length"], 65)
        self.assertEqual(match["font"]["source_offset"], 0xF8200)
        self.assertEqual(len(match["calls"]), 4)
        self.assertEqual(match["return_offset"], start + 64)

    def test_identity_gate_rejects_wrong_rom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.gbc"
            path.write_bytes(bytes(0x100))
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                MODULE.inspect(path, "gold-silver", "0" * 64)


if __name__ == "__main__":
    unittest.main()
