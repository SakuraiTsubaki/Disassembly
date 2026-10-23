import importlib.util,unittest
from pathlib import Path
R=Path(__file__).parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/extract_gen2_footprints.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_dimensions(self):self.assertEqual((M.SLOTS,M.TILES_PER_SLOT,M.LENGTH),(256,4,8192))
 def test_unique_offset(self):self.assertEqual(M.unique_offset(b'xxATLASyy',b'ATLAS'),2)
 def test_non_unique_rejected(self):
  with self.assertRaises(ValueError):M.unique_offset(b'ATLASATLAS',b'ATLAS')
if __name__=='__main__':unittest.main()
