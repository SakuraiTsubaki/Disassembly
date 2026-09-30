import importlib.util, struct, unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'extract_gb_2bpp.py'; S=importlib.util.spec_from_file_location('extract_gb_2bpp',P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_partial_final_row_and_shape(self):
  png=M.render(bytes(3*16),2); self.assertEqual(struct.unpack('>II',png[16:24]),(32,32)); self.assertEqual(png,M.render(bytes(3*16),2))
 def test_report_omits_source_bytes(self):
  png,r=M.extract(bytes(range(128)),16,3,2); self.assertEqual((r['source_offset'],r['source_length'],r['logical_height']),(16,48,16)); self.assertNotIn('source_bytes',r); self.assertTrue(png.startswith(b'\x89PNG'))
 def test_invalid_input(self):
  with self.assertRaises(ValueError): M.render(bytes(15),1)
if __name__=='__main__': unittest.main()
