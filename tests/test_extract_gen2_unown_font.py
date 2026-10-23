import importlib.util,unittest
from pathlib import Path
R=Path(__file__).parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/extract_gen2_unown_font.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_unique_offset(self):self.assertEqual(M.unique_offset(b'xxFONTyy',b'FONT'),2)
 def test_duplicate_or_missing_rejected(self):
  with self.assertRaises(ValueError):M.unique_offset(b'FONTxxFONT',b'FONT')
  with self.assertRaises(ValueError):M.unique_offset(b'none',b'FONT')
 def test_asset_length(self):self.assertEqual(M.LENGTH,432)
if __name__=='__main__':unittest.main()
