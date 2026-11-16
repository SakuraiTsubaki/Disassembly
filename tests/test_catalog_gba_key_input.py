import importlib.util
import pathlib
import struct
import unittest


TOOL = pathlib.Path(__file__).parents[1] / "tools" / "catalog_gba_key_input.py"
SPEC = importlib.util.spec_from_file_location("catalog_gba_key_input", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class KeyInputCatalogTests(unittest.TestCase):
    def test_profiles_are_pinned_and_access_is_explicit(self):
        self.assertEqual(MODULE.PROFILES["rs"]["access"], "direct")
        self.assertEqual(MODULE.PROFILES["emerald"]["access"], "pointer")
        self.assertEqual(MODULE.PROFILES["frlg"]["access"], "pointer")
        self.assertTrue(all(len(item["commit"]) == 40
                            for item in MODULE.PROFILES.values()))

    def test_templates_preserve_function_lengths(self):
        self.assertEqual(len(MODULE.INIT_TEMPLATE) * 2, 28)
        self.assertEqual(len(MODULE.read_template("direct")) * 2, 148)
        self.assertEqual(len(MODULE.read_template("pointer")) * 2, 150)

    def test_masked_match_accepts_only_wildcard_literals(self):
        template = MODULE.read_template("direct")
        words = [0 if value is None else value for value in template]
        data = b"\0\0" + struct.pack(f"<{len(words)}H", *words) + b"\0\0"
        self.assertEqual(MODULE.matching_offsets(data, template), [2])
        words[1] ^= 1
        changed = b"\0\0" + struct.pack(f"<{len(words)}H", *words) + b"\0\0"
        self.assertEqual(MODULE.matching_offsets(changed, template), [])

    def test_source_is_semantic_not_raw_halfword_dump(self):
        source = MODULE.source_text("pointer")
        for token in ("InitKeys:", "ReadKeys:", "gSaveBlock2Ptr", "REG_KEYINPUT"):
            self.assertIn(token, source.replace("0x04000130", "REG_KEYINPUT"))
        self.assertNotIn(".hword", source)


if __name__ == "__main__":
    unittest.main()
