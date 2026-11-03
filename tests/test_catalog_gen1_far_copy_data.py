import unittest
from tools import catalog_gen1_far_copy_data as M
class FarCopyDataTests(unittest.TestCase):
 def test_decode(self):
  c=bytes.fromhex("ea34c2f0b8f5fa34c2e0b8ea0020cd2301f1e0b8ea0020c9");f=M.decode_classic(c+b"x",24,0x123);self.assertEqual(f["wBuffer"],"0xC234");self.assertEqual(f["copy_data_address"],"0x0123")
 def test_rejects_mismatched_restore(self):
  c=bytearray.fromhex("ea34c2f0b8f5fa34c2e0b8ea0020cd2301f1e0b8ea0120c9");self.assertIsNone(M.decode_classic(bytes(c),24,0x123))
 def test_yellow(self):
  c=bytes.fromhex("ea22d1f0b8f5fa22d1cd7e3ecdb100f1cd7e3ec9");f=M.decode_yellow(c,0,0xB1);self.assertEqual(f["length"],20);self.assertEqual(f["bankswitch_common_address"],"0x3E7E")
 def test_length(self):self.assertEqual(M.LENGTH,24)
if __name__=="__main__":unittest.main()
