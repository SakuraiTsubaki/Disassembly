import unittest
from tools import catalog_gen2_crystal_wram_access as M
class WramAccessTests(unittest.TestCase):
 def test_decode(self):
  c=bytes.fromhex("e08bf070f5f08be070cdf22ff1e070c9e08bf070f5f08be0707ee08bf1e070f08bc9e08bf070f5f08be0702a666ff1e070c9");f=M.decode(c,0,0x2ff2);self.assertEqual(f["rWBK"],"0xFF70");self.assertEqual(f["hFarByte"],"0xFF8B")
 def test_rejects_wrong_copy_target(self):
  c=bytes.fromhex("e08bf070f5f08be070cdf22ff1e070c9e08bf070f5f08be0707ee08bf1e070f08bc9e08bf070f5f08be0702a666ff1e070c9");self.assertIsNone(M.decode(c,0,0x1234))
 def test_length(self):self.assertEqual(M.SUITE_LENGTH,50)
if __name__=="__main__":unittest.main()
