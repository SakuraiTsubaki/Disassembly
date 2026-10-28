import importlib.util
import pathlib
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_frlg_species_sprites.py"
SPEC = importlib.util.spec_from_file_location("catalog_frlg_species_sprites", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrlgSpeciesSpriteCatalogTests(unittest.TestCase):
    def test_sprite_and_palette_entries(self):
        data = bytearray(0x200)
        table = 0x20
        species = 3
        source = 0x100
        data[source] = 0x10
        entry = table + species * 8
        data[entry:entry + 4] = (MODULE.ROM_BASE + source).to_bytes(4, "little")
        data[entry + 4:entry + 6] = (0x800).to_bytes(2, "little")
        data[entry + 6:entry + 8] = species.to_bytes(2, "little")
        self.assertEqual(MODULE.table_entry(bytes(data), table, species, True)["source_offset"], source)
        data[entry + 4:entry + 6] = species.to_bytes(2, "little")
        data[entry + 6:entry + 8] = b"\0\0"
        self.assertEqual(MODULE.table_entry(bytes(data), table, species, False)["tag"], species)

    def test_release_prefix(self):
        self.assertEqual(MODULE.prefix("FireRed", "bpr-j-rev1-retail", 1),
                         ("firered-jp-rev1", "jp"))


if __name__ == "__main__":
    unittest.main()
