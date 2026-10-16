import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_multiply_core.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_gold_layout(self):
  d=bytes(0x4000)+M.expected(0xb5);f=M.inspect(d,0x4000,0x4060);self.assertEqual((f['bank'],f['address'],f['length']),(1,0x4000,96));self.assertEqual(f['hram_layout']['multiplier'],0xffb9);self.assertEqual(f['hram_layout']['product'],[0xffb5,0xffb6,0xffb7,0xffb8])
 def test_crystal_layout(self):self.assertEqual(M.inspect(M.expected(0xb3),0,96)['hram_layout']['multiplier'],0xffb7)
 def test_rejects_bad_loop_target(self):
  d=bytearray(M.expected(0xb5));d[21]=0x21;self.assertIsNone(M.inspect(bytes(d),0,96))
if __name__=='__main__':unittest.main()
