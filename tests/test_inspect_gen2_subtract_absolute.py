import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_subtract_absolute.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_extracts_both_paths(self):
  d=bytes(0x80)+M.CODE;f=M.inspect(d,0x80);self.assertEqual(f['nonnegative_return_offset'],0x81);self.assertEqual(f['negative_path_offset'],0x82);self.assertEqual(f['preserved_registers'],['BC','DE','HL'])
 def test_rejects_missing_carry_set(self):
  d=bytearray(M.CODE);d[5]=0x3f;self.assertIsNone(M.inspect(bytes(d),0))
if __name__=='__main__':unittest.main()
