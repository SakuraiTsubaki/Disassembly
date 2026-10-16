import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen1_multiply_core.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_layout_and_bank(self):
  d=bytes(0x4000)+M.expected(0x95);f=M.inspect(d,0x4000,0x4064);self.assertEqual((f['bank'],f['address'],f['length']),(1,0x4000,100));self.assertEqual(f['hram_layout']['multiplier'],0xff99);self.assertEqual(f['hram_layout']['product'],[0xff95,0xff96,0xff97,0xff98])
 def test_rejects_wrong_shift(self):
  d=bytearray(M.expected(0x95));d[59]=0x87;self.assertIsNone(M.inspect(bytes(d),0,100))
if __name__=='__main__':unittest.main()
