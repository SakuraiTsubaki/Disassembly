import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SPEC=importlib.util.spec_from_file_location('m',ROOT/'tools/inspect_gen2_random_range.py');M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
def routine(random=0x305e,hadd=0xe3,divide=0x3171):return bytes((0xc5,0x4f,0xaf,0x91,0x91,0x30,0xfd,0x81,0x47,0xc5,0xcd,random&255,random>>8,0xf0,hadd,0x4f,0x80,0x38,0xf7,0x79,0xc1,0xcd,divide&255,divide>>8,0xc1,0xc9))
class Tests(unittest.TestCase):
 def test_extracts_dependencies_and_loops(self):
  f=M.inspect(routine(),0,0x305e,0xffe3);self.assertEqual(f['dependencies']['SimpleDivide']['address'],0x3171);self.assertEqual(f['control_flow']['rejection_loop'],{'from_offset':17,'to_offset':10})
 def test_rejects_wrong_random(self):self.assertIsNone(M.inspect(routine(),0,0x305f,0xffe3))
 def test_rejects_wrong_hram(self):self.assertIsNone(M.inspect(routine(),0,0x305e,0xffe1))
 def test_rejects_broken_branch(self):
  b=bytearray(routine());b[18]=0xf8;self.assertIsNone(M.inspect(bytes(b),0,0x305e,0xffe3))
if __name__=='__main__':unittest.main()
