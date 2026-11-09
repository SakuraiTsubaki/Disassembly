import unittest

from tools import catalog_gen1_delay as delay


class DelayCatalogToolTests(unittest.TestCase):
    def test_decode_delay_frame(self):
        code = bytes.fromhex("3e01e0d676f0d6a720fac9")
        found = delay.decode_delay_frame(code, 0)
        self.assertIsNotNone(found)
        self.assertEqual(found["h_vblank_occurred_address"], 0xFFD6)

    def test_rejects_mismatched_hram_offsets(self):
        code = bytes.fromhex("3e01e0d676f0d7a720fac9")
        self.assertIsNone(delay.decode_delay_frame(code, 0))

    def test_delay_frames_must_call_target(self):
        data = bytes.fromhex("cd00000d20fac9cd01000d20fac9")
        self.assertEqual(len(delay.locate_delay_frames(data, 0)), 1)
        self.assertEqual(delay.locate_delay_frames(data, 0)[0]["address"], 0)


if __name__ == "__main__":
    unittest.main()
