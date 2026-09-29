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


inspector = load_module("inspect_gba_rom", ROOT / "tools" / "inspect_gba_rom.py")


def fixture() -> bytes:
    data = bytearray(0x200)
    data[0:4] = bytes.fromhex("00 00 00 ea")
    data[0x04:0xA0] = inspector.NINTENDO_LOGO
    data[0xA0:0xAC] = b"POKEMON RUBY"
    data[0xAC:0xB0] = b"AXVE"
    data[0xB0:0xB2] = b"01"
    data[0xB2] = 0x96
    data[0xBC] = 1
    data[0xBD] = (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF
    return bytes(data)


class InspectGameBoyAdvanceRomTests(unittest.TestCase):
    def test_valid_header(self):
        result = inspector.inspect_bytes(fixture(), filename="fixture.gba")
        self.assertEqual(result["filename"], "fixture.gba")
        self.assertEqual(result["header"]["title"], "POKEMON RUBY")
        self.assertEqual(result["header"]["game_code"], "AXVE")
        self.assertEqual(result["header"]["software_version"], 1)
        self.assertTrue(result["validation"]["nintendo_logo_valid"])
        self.assertTrue(result["validation"]["fixed_value_valid"])
        self.assertTrue(result["validation"]["reserved_area_valid"])
        self.assertTrue(result["validation"]["header_checksum_valid"])

    def test_header_corruption_is_reported(self):
        data = bytearray(fixture())
        data[0xA0] ^= 0x01
        result = inspector.inspect_bytes(bytes(data))
        self.assertFalse(result["validation"]["header_checksum_valid"])

    def test_reserved_byte_is_reported(self):
        data = bytearray(fixture())
        data[0xB5] = 1
        result = inspector.inspect_bytes(bytes(data))
        self.assertFalse(result["validation"]["reserved_area_valid"])

    def test_short_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            inspector.inspect_bytes(bytes(0xBF))


if __name__ == "__main__":
    unittest.main()

