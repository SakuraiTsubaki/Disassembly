import hashlib
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "locate_gba_lz77_hash", ROOT / "tools/locate_gba_lz77_hash.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def literal_stream(raw: bytes) -> bytes:
    output = bytearray((0x10, *len(raw).to_bytes(3, "little")))
    for start in range(0, len(raw), 8):
        output.append(0)
        output.extend(raw[start : start + 8])
    return bytes(output)


class LocateGbaLz77HashTests(unittest.TestCase):
    def test_finds_only_exact_decoded_hash(self):
        wanted = bytes(range(16))
        other = bytes(reversed(range(16)))
        rom = b"prefix" + literal_stream(other) + b"gap" + literal_stream(wanted)
        matches = MODULE.locate(rom, len(wanted), hashlib.sha256(wanted).hexdigest())
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source_offset"], len(b"prefix") + len(literal_stream(other)) + len(b"gap"))

    def test_missing_hash_is_rejected_by_inspect(self):
        path = ROOT / "tests" / "__missing_test_rom__.gba"
        with self.assertRaises(OSError):
            MODULE.inspect(path, 32, "0" * 64)


if __name__ == "__main__":
    unittest.main()
