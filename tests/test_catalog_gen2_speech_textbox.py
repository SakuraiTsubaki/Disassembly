import importlib.util, pathlib, unittest
TOOL = pathlib.Path(__file__).parents[1] / "tools/catalog_gen2_speech_textbox.py"
SPEC = importlib.util.spec_from_file_location("catalog_gen2_speech_textbox", TOOL)
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)
class SpeechTextboxCatalogTests(unittest.TestCase):
    def test_decodes_verified_tail_target(self):
        code = bytes.fromhex("2190c406040e12c33412")
        data = bytes(0x200) + code
        match = MODULE.locate(data, 0x1234)[0]
        self.assertEqual(match["tilemap_pointer"], 0xC490)
        self.assertEqual((match["inner_height"], match["inner_width"]), (4, 18))
    def test_rejects_wrong_textbox_target(self):
        code = bytes.fromhex("2190c406040e12c33412")
        self.assertIsNone(MODULE.decode_candidate(code, 0, 0x9999))
if __name__ == "__main__": unittest.main()

