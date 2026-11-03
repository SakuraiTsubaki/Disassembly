import unittest
from tools import catalog_gen3_div_bios_stub as M
class DivBiosStubTests(unittest.TestCase):
 def test_signature(self):self.assertEqual(M.SIGNATURE,bytes.fromhex("06df7047"))
 def test_locate(self):self.assertEqual(M.locate(M.SIGNATURE+b"x"+M.SIGNATURE),[0,5])
 def test_layout(self):self.assertEqual(M.LZ_RELATIVE,-4)
if __name__=="__main__":unittest.main()
