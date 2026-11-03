import unittest
from tools import catalog_gen2_far_access as M
class FarAccessTests(unittest.TestCase):
 def test_gs(self):
  c=bytes.fromhex("ea48d1f09ff5fa48d1d77eea48d1f1d7fa48d1c9ea48d1f09ff5fa48d1d72a666ff1d7c9");f=M.decode_gs(c,0);self.assertEqual(f["GetFarByte"]["length"],20);self.assertEqual(f["GetFarWord"]["length"],16)
 def test_crystal(self):
  c=bytes.fromhex("e08bf09df5f08bd77ee08bf1d7f08bc9e08bf09df5f08bd72a666ff1d7c9");f=M.decode_crystal(c,0);self.assertEqual(f["GetFarByte"]["far_byte_storage"],"0xFF8B")
 def test_lengths(self):self.assertEqual(M.LENGTHS["gs"]["GetFarWord"],16);self.assertEqual(M.LENGTHS["crystal"]["GetFarByte"],16)
if __name__=="__main__":unittest.main()
