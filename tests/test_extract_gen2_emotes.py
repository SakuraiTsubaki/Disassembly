import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("emotes", ROOT / "tools/extract_gen2_emotes.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EmoteExtractorTests(unittest.TestCase):
    def test_dimensions(self):
        self.assertEqual((len(MODULE.EMOTE_NAMES), len(MODULE.EFFECTS)), (8, 4))
        self.assertEqual((MODULE.EMOTE_LENGTH, MODULE.LENGTH), (512, 608))

    def test_emote_reordering(self):
        raw = b"".join(bytes([index]) * 64 for index in range(8))
        arranged = MODULE.arrange_emotes(raw)
        self.assertEqual(len(arranged), 512)
        self.assertEqual(arranged[:32], bytes([0]) * 32)
        self.assertEqual(arranged[32:64], bytes([1]) * 32)

    def test_effect_padding(self):
        raw = bytes([1]) * 16 + bytes([2]) * 32 + bytes([3]) * 32 + bytes([4]) * 16
        arranged = MODULE.arrange_effects(raw)
        self.assertEqual(len(arranged), 128)
        self.assertEqual(arranged[64:80], bytes(16))
        self.assertEqual(arranged[-16:], bytes(16))

    def test_unique_offset(self):
        self.assertEqual(MODULE.unique_offset(b"xxEMOTESyy", b"EMOTES"), 2)

    def test_non_unique_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_offset(b"EMOTESEMOTES", b"EMOTES")


if __name__ == "__main__":
    unittest.main()
