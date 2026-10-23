import importlib.util,unittest
from pathlib import Path
R=Path(__file__).parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/locate_gba_trainer_id_helpers.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_unique_aligned_signature(self):self.assertEqual(M.unique_offset(b'xxABCDyy',b'ABCD'),2)
 def test_rejects_duplicate_or_unaligned(self):
  with self.assertRaises(ValueError):M.unique_offset(b'ABCDxxABCD',b'ABCD')
  with self.assertRaises(ValueError):M.unique_offset(b'xABCD',b'ABCD')
 def test_function_argument(self):self.assertEqual(M.parse_function('SetTrainerId:0x10:16'),('SetTrainerId',16,16))
if __name__=='__main__':unittest.main()
