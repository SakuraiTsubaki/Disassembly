import unittest
from tools import catalog_gen3_rl_bios_stubs as M
class RlBiosStubTests(unittest.TestCase):
 def test_signatures(self):self.assertEqual({k:v["swi"] for k,v in M.FUNCTIONS.items()},{"RLUnCompVram":0x15,"RLUnCompWram":0x14})
 def test_locate(self):self.assertEqual(M.locate(b"x"+bytes.fromhex("15df7047")+b"y",bytes.fromhex("15df7047")),[1])
 def test_layouts(self):self.assertEqual(M.LZ_RELATIVE["rs"]["RLUnCompVram"],12);self.assertEqual(M.LZ_RELATIVE["emerald"]["RLUnCompWram"],24)
if __name__=="__main__":unittest.main()
