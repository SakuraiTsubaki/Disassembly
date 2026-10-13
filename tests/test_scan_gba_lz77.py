from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("scan_gba_lz77", ROOT / "tools" / "scan_gba_lz77.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def literal_stream(raw: bytes) -> bytes:
    result = bytearray(b"\x10" + len(raw).to_bytes(3, "little"))
    for offset in range(0, len(raw), 8):
        result.append(0)
        result.extend(raw[offset : offset + 8])
    return bytes(result)


class ScanGbaLz77Tests(unittest.TestCase):
    def test_bounded_scan_reports_hashes_without_bytes(self):
        first = literal_stream(bytes(range(32)))
        second = literal_stream(bytes(reversed(range(32))))
        rom = b"prefix" + first + b"gap" + second + b"suffix"
        report = module.scan(rom, 0, len(rom), 32)
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual([item["source_offset"] for item in report["candidates"]], [6, 6 + len(first) + 3])
        self.assertTrue(all(item["decompressed_length"] == 32 for item in report["candidates"]))
        self.assertEqual(
            set(report["candidates"][0]),
            {"source_offset", "compressed_length", "compressed_sha256", "decompressed_length", "decompressed_sha256"},
        )
        self.assertFalse(report["raw_rom_bytes_included"])

    def test_identity_and_bounds_are_gated(self):
        rom = literal_stream(bytes(range(32)))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            module.scan(rom, 0, len(rom), 32, "0" * 64)
        with self.assertRaisesRegex(ValueError, "invalid scan range"):
            module.scan(rom, 4, 4, 32)
        with self.assertRaisesRegex(ValueError, "positive"):
            module.scan(rom, 0, len(rom), 0)


if __name__ == "__main__":
    unittest.main()
