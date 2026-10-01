import importlib.util,struct,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'compose_gb_1bpp_tilemap.py';S=importlib.util.spec_from_file_location('compose1',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_index_and_blank(self):
  png=M.render(bytes([0xff]*8+[0]*8),bytes([0x60,0x7f,0x61]),0x60,{0x7f});self.assertEqual(struct.unpack('>II',png[16:24]),(96,32));self.assertEqual(png,M.render(bytes([0xff]*8+[0]*8),bytes([0x60,0x7f,0x61]),0x60,{0x7f}))
 def test_report_omits_bytes(self):
  _,r=M.compose(bytes(64),0,2,32,3,0x60,{0});self.assertEqual((r['tiles_length'],r['tilemap_length']),(16,3));self.assertNotIn('tiles_bytes',r)
 def test_bad_id(self):
  with self.assertRaises(ValueError): M.render(bytes(8),bytes([2]),0,set())
if __name__=='__main__':unittest.main()
