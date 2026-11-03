import unittest
from tools import catalog_gen2_crystal_swap_bytes as M
class SwapBytesTests(unittest.TestCase):
 def test_decode(self):self.assertEqual(M.decode(M.SIGNATURE,0)["length"],13)
 def test_rejects(self):self.assertIsNone(M.decode(M.SIGNATURE[:-1]+b"x",0))
 def test_length(self):self.assertEqual(M.LENGTH,13)
if __name__=="__main__":unittest.main()
