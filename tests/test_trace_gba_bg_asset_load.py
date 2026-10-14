import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trace_gba_bg_asset_load", ROOT / "tools/trace_gba_bg_asset_load.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TraceGbaBackgroundAssetLoadTests(unittest.TestCase):
    def test_r1_asset_and_delayed_call_are_traced(self):
        data = bytearray(0x100)
        source = 0x80
        data[source : source + 4] = bytes((0x10, 0x20, 0, 0))
        data[0x20:0x30] = bytes.fromhex("07490024009400200022002300f000f8")
        data[0x40:0x44] = (MODULE._BASE.ROM_BASE + source).to_bytes(4, "little")
        report = MODULE.trace_background_load(bytes(data), source)
        load = report["background_loads"][0]
        self.assertEqual(load["asset_argument_register"], 1)
        self.assertEqual(load["register_immediates"], {"r4": 0, "r0": 0, "r2": 0, "r3": 0})
        self.assertEqual(load["call_target"], MODULE._BASE.ROM_BASE + 0x30)
        self.assertEqual(load["loader_sequence_length"], 16)

    def test_r0_direct_loader_is_not_bg_api_call(self):
        data = bytearray(0x100)
        source = 0x80
        data[source : source + 4] = bytes((0x10, 0x20, 0, 0))
        data[0x20:0x28] = bytes.fromhex("0748084900f000f8")
        data[0x40:0x44] = (MODULE._BASE.ROM_BASE + source).to_bytes(4, "little")
        data[0x44:0x48] = (0x06008000).to_bytes(4, "little")
        report = MODULE.trace_background_load(bytes(data), source)
        self.assertEqual(report["background_loads"], [])


if __name__ == "__main__":
    unittest.main()
