import unittest

from tools import catalog_gen2_delay as delay


class DelayCatalogToolTests(unittest.TestCase):
    def test_decode_pair(self):
        code = bytes.fromhex("3e01ea1ecf7600fa1ecfa720f8c9cd00000d20fac9")
        found = delay.decode(code, 0)
        self.assertIsNotNone(found)
        self.assertEqual(found["delay_frame_address"], 0)
        self.assertEqual(found["delay_frames_address"], 14)
        self.assertEqual(found["w_vblank_occurred_address"], 0xCF1E)

    def test_rejects_mismatched_wait_flag(self):
        code = bytes.fromhex("3e01ea1ecf7600fa1fcfa720f8c9cd00000d20fac9")
        self.assertIsNone(delay.decode(code, 0))

    def test_rejects_wrong_call_target(self):
        code = bytes.fromhex("3e01ea1ecf7600fa1ecfa720f8c9cd01000d20fac9")
        self.assertIsNone(delay.decode(code, 0))


if __name__ == "__main__":
    unittest.main()
