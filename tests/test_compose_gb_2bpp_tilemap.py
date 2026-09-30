import importlib.util, struct, unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'compose_gb_2bpp_tilemap.py'; S=importlib.util.spec_from_file_location('compose',P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_composes_and_pads_blank_id(self):
  tiles=bytes([0xff,0]*8+[0,0xff]*8); png=M.render(tiles,bytes([0,1,0xfe,0]),2,2,{0xfe}); self.assertEqual(struct.unpack('>II',png[16:24]),(32,32)); self.assertEqual(png,M.render(tiles,bytes([0,1,0xfe,0]),2,2,{0xfe}))
 def test_report_has_hashes_not_bytes(self):
  rom=bytes(128); png,r=M.compose(rom,0,2,64,2,2,{0}); self.assertEqual((r['tiles_length'],r['tilemap_length']),(32,4)); self.assertNotIn('tiles_bytes',r); self.assertTrue(png.startswith(b'\x89PNG'))
 def test_rejects_unknown_tile(self):
  with self.assertRaises(ValueError): M.render(bytes(16),bytes([1]),1,1,set())
 def test_extra_tile_id_is_remapped(self):
  rom=bytes(32)+bytes([0xfd])+bytes(15)+bytes([0xff,0]*8); png,r=M.compose(rom,0,2,32,1,1,set(),extra_offset=48,extra_count=1,extra_first_id=0xfd); self.assertIn('extra_tiles',r); self.assertTrue(png.startswith(b'\x89PNG'))
if __name__=='__main__': unittest.main()
