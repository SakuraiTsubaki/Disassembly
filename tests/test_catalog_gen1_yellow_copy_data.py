import unittest
from tools import catalog_gen1_yellow_copy_data as M
class YellowCopyDataTests(unittest.TestCase):
 def test_decode(self):
  c=bytes.fromhex("78a7280c79a7280104cd10000520fac92a12130d20fac9");f=M.decode(c,0);self.assertEqual(f["length"],23);self.assertEqual(f["copybytes_address"],16)
 def test_rejects_red_loop(self):self.assertEqual(M.locate(bytes.fromhex("2a12130b79b020f8c9")),[])
 def test_length(self):self.assertEqual(M.LENGTH,23)
if __name__=="__main__":unittest.main()
