import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_simple_divide.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_accepts_shape(self):
  f=M.inspect(M.SHAPE,0);self.assertEqual(f['output'],{'quotient':'B','remainder':'A'});self.assertEqual(f['control_flow']['subtract_loop'],{'from_offset':4,'to_offset':2})
 def test_rejects_broken_branch(self):
  b=bytearray(M.SHAPE);b[5]^=1;self.assertIsNone(M.inspect(bytes(b),0))
if __name__=='__main__':unittest.main()
