import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_divide_core.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_gold_layout(self):
  d=bytes(0x4000)+M.expected(0xb5);f=M.inspect(d,0x4000);self.assertEqual((f['bank'],f['length'],f['range_end_exclusive']),(1,131,0x4083));self.assertEqual(f['hram_layout']['divisor'],0xffb9);self.assertEqual(f['hram_layout']['quotient'],[0xffb5,0xffb6,0xffb7,0xffb8])
 def test_crystal_layout(self):self.assertEqual(M.inspect(M.expected(0xb3),0)['hram_layout']['remainder'],0xffb7)
 def test_rejects_bad_done_branch(self):
  d=bytearray(M.expected(0xb5));d[45]=0x41;self.assertIsNone(M.inspect(bytes(d),0))
if __name__=='__main__':unittest.main()
