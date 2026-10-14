import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trace_gba_lz77_load", ROOT / "tools/trace_gba_lz77_load.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TraceGbaLz77LoadTests(unittest.TestCase):
    def test_literal_load_and_direct_call_are_traced(self):
        data = bytearray(0x100)
        source = 0x80
        data[source : source + 4] = bytes((0x10, 0x20, 0, 0))
        data[0x20:0x28] = bytes.fromhex("0748084900f000f8")
        data[0x40:0x44] = (MODULE.ROM_BASE + source).to_bytes(4, "little")
        data[0x44:0x48] = (0x06008000).to_bytes(4, "little")
        report = MODULE.trace(bytes(data), source)
        self.assertEqual(report["pointer_locations"], [0x40])
        reference = report["thumb_references"][0]
        self.assertEqual(reference["instruction_offset"], 0x20)
        self.assertEqual(reference["destination"], 0x06008000)
        self.assertEqual(reference["call_target"], MODULE.ROM_BASE + 0x28)
        self.assertFalse(report["raw_bytes_published"])

    def test_data_table_pointer_without_code_reference_is_retained(self):
        data = bytearray(0x100)
        source = 0x80
        data[source : source + 4] = bytes((0x10, 0x20, 0, 0))
        data[0x40:0x44] = (MODULE.ROM_BASE + source).to_bytes(4, "little")
        report = MODULE.trace(bytes(data), source, search_back=0x20)
        self.assertEqual(report["pointer_locations"], [0x40])
        self.assertEqual(report["thumb_references"], [])

    def test_rejects_non_lz77_source(self):
        with self.assertRaisesRegex(ValueError, "LZ77"):
            MODULE.trace(bytes(32), 4)


if __name__ == "__main__":
    unittest.main()
