from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inspector = load_module("inspect_gb_rom", ROOT / "tools" / "inspect_gb_rom.py")


def fixture() -> bytes:
    data = bytearray(0x8000)
    data[0x104:0x134] = inspector.NINTENDO_LOGO
    data[0x134:0x140] = b"POKEMON RED\0"
    data[0x146] = 0x03
    data[0x147] = 0x13
    data[0x149] = 0x02
    data[0x14B] = 0x01
    data[0x14C] = 0x01
    checksum = 0
    for value in data[0x134:0x14D]:
        checksum = (checksum - value - 1) & 0xFF
    data[0x14D] = checksum
    global_checksum = (sum(data[:0x14E]) + sum(data[0x150:])) & 0xFFFF
    data[0x14E:0x150] = global_checksum.to_bytes(2, "big")
    return bytes(data)


class InspectGameBoyRomTests(unittest.TestCase):
    def test_valid_header(self):
        result = inspector.inspect_bytes(fixture(), filename="fixture.gb")
        self.assertEqual(result["filename"], "fixture.gb")
        self.assertEqual(result["header"]["title"], "POKEMON RED")
        self.assertEqual(result["header"]["revision"], 1)
        self.assertTrue(result["validation"]["nintendo_logo_valid"])
        self.assertTrue(result["validation"]["header_checksum_valid"])
        self.assertTrue(result["validation"]["global_checksum_valid"])

    def test_corruption_is_reported(self):
        data = bytearray(fixture())
        data[0x200] ^= 0xFF
        result = inspector.inspect_bytes(bytes(data))
        self.assertTrue(result["validation"]["header_checksum_valid"])
        self.assertFalse(result["validation"]["global_checksum_valid"])

    def test_cgb_flag_is_not_part_of_title(self):
        data = bytearray(fixture())
        data[0x143] = 0x80
        checksum = 0
        for value in data[0x134:0x14D]:
            checksum = (checksum - value - 1) & 0xFF
        data[0x14D] = checksum
        global_checksum = (sum(data[:0x14E]) + sum(data[0x150:])) & 0xFFFF
        data[0x14E:0x150] = global_checksum.to_bytes(2, "big")
        result = inspector.inspect_bytes(bytes(data))
        self.assertEqual(result["header"]["title"], "POKEMON RED")
        self.assertEqual(result["header"]["cgb_flag"], 0x80)

    def test_short_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            inspector.inspect_bytes(bytes(0x14F))


if __name__ == "__main__":
    unittest.main()
