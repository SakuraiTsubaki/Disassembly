import hashlib
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("locate_gb_1bpp_loader", ROOT / "tools/locate_gb_1bpp_loader.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LocateGameBoy1bppLoaderTests(unittest.TestCase):
    def make_rom(self):
        rom = bytearray(0x20000)
        loader = 0x3680
        address = 0x5A80
        bank = 4
        payload = bytes((index * 29 + 7) & 0xFF for index in range(0x400))
        source_offset = MODULE.banked_offset(bank, address)
        rom[source_offset:source_offset + len(payload)] = payload
        code = bytes.fromhex(
            "f0 40 cb 7f 20 0e 21 80 5a 11 00 88 01 00 04 3e 04 "
            "c3 2b 18 11 80 5a 21 00 88 01 80 04 c3 86 18"
        )
        rom[loader:loader + len(code)] = code
        return bytes(rom), loader, source_offset, payload

    def test_locates_loader_and_hashes_asset_without_bytes(self):
        rom, loader, source_offset, payload = self.make_rom()
        result = MODULE.report(rom)
        self.assertFalse(result["raw_rom_bytes_included"])
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["loader_offset"], loader)
        self.assertEqual(candidate["source_offset"], source_offset)
        self.assertEqual(candidate["tile_count"], 128)
        self.assertEqual(candidate["source_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertTrue(candidate["raw_bytes_omitted"])
        self.assertNotIn("bytes", candidate)

    def test_rejects_invalid_length_and_identity(self):
        rom, _, _, _ = self.make_rom()
        with self.assertRaises(ValueError):
            MODULE.locate(rom, 7)
        with self.assertRaisesRegex(ValueError, "ROM SHA-256 mismatch"):
            MODULE.report(rom, expected_sha256="00" * 32)

    def test_invalid_duplicate_pointer_is_not_a_candidate(self):
        rom, loader, _, _ = self.make_rom()
        damaged = bytearray(rom)
        damaged[loader + 21] ^= 1
        self.assertEqual(MODULE.locate(bytes(damaged)), [])


if __name__ == "__main__":
    unittest.main()
