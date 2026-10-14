import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "inspect_gba_species_sprite", ROOT / "tools/inspect_gba_species_sprite.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InspectGbaSpeciesSpriteTests(unittest.TestCase):
    def test_entry_table_and_thumb_reference(self):
        data = bytearray(0x200)
        species = 3
        table = 0x80
        entry = table + species * 8
        source = 0x180
        data[source : source + 4] = bytes((0x10, 0x00, 0x10, 0x00))
        data[entry : entry + 4] = (MODULE._BASE.ROM_BASE + source).to_bytes(4, "little")
        data[entry + 4 : entry + 6] = (0x800).to_bytes(2, "little")
        data[entry + 6 : entry + 8] = species.to_bytes(2, "little")
        data[0x40:0x44] = (MODULE._BASE.ROM_BASE + table).to_bytes(4, "little")
        data[0x20:0x22] = (0x4807).to_bytes(2, "little")

        report = MODULE.inspect_bytes(bytes(data), source, species)
        result = report["entries"][0]
        self.assertEqual(result["size"], 0x800)
        self.assertEqual(result["tag"], species)
        self.assertEqual(result["table_offset"], table)
        self.assertEqual(result["table_pointer_locations"], [0x40])
        self.assertEqual(result["table_thumb_references"][0]["instruction_offset"], 0x20)

    def test_wrong_species_is_rejected(self):
        data = bytearray(0x100)
        data[0x80:0x84] = bytes((0x10, 0x20, 0, 0))
        with self.assertRaisesRegex(ValueError, "found 0"):
            MODULE.inspect_bytes(bytes(data), 0x80, 1)


if __name__ == "__main__":
    unittest.main()
