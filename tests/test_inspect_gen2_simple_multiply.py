import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_simple_multiply.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_extracts_loop_and_boundary(self):
  d=bytes(0x100)+M.CODE+bytes(16);f=M.inspect(d,0x100);self.assertEqual((f['length'],f['range_end_exclusive']),(11,0x10b));self.assertEqual(f['loop']['target_offset'],0x105);self.assertEqual(f['preserved_registers'],['BC'])
 def test_rejects_wrong_branch(self):
  d=bytearray(M.CODE);d[8]=0xfd;self.assertIsNone(M.inspect(bytes(d),0))
if __name__=='__main__':unittest.main()
