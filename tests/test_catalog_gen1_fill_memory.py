import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).parents[1] / "tools" / "catalog_gen1_fill_memory.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen1_fill_memory", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Tests(unittest.TestCase):
    def test_both_profiles_locate(self):
        for profile in MODULE.PROFILES.values():
            data = b"x" + profile["routine"] + b"y"
            self.assertEqual(MODULE.locate(data, profile["routine"]), [1])

    def test_sources_use_mnemonics(self):
        for profile in MODULE.PROFILES:
            source = MODULE.source_text(profile)
            self.assertIn("FillMemory::", source)
            self.assertIn("ld [hli], a", source)
            self.assertNotIn("db ", source.lower())

    def test_yellow_variant_is_distinct(self):
        self.assertGreater(
            len(MODULE.PROFILES["yellow"]["routine"]),
            len(MODULE.PROFILES["classic"]["routine"]),
        )


if __name__ == "__main__":
    unittest.main()
