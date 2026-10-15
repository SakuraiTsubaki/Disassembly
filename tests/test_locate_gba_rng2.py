import importlib.util,struct,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/locate_gba_rng2.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_hits_even_offsets(self):
  p=(1,2);d=bytearray(12);d[4:8]=struct.pack('<2H',*p);self.assertEqual(M.hits(bytes(d),p),[4])
 def test_rejects_missing_pair(self):
  with self.assertRaises(ValueError):M.locate(b'\0'*64)
if __name__=='__main__':unittest.main()
