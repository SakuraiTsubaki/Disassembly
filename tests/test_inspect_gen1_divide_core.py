import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen1_divide_core.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_layout_and_length(self):
  d=bytes(0x4000)+M.expected(0x95);f=M.inspect(d,0x4000);self.assertEqual((f['bank'],f['length'],f['range_end_exclusive']),(1,136,0x4088));self.assertEqual(f['hram_layout']['divisor'],0xff99);self.assertEqual(f['hram_layout']['quotient'],[0xff95,0xff96,0xff97,0xff98])
 def test_rejects_bad_loop_branch(self):
  d=bytearray(M.expected(0x95));d[119]=0x9c;self.assertIsNone(M.inspect(bytes(d),0))
if __name__=='__main__':unittest.main()
