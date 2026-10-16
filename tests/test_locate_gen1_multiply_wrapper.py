import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/locate_gen1_multiply_wrapper.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_locates_farcall(self):
  d=bytearray(0x10000);d[0x100:0x10d]=bytes((0xe5,0xc5,0x21,0x00,0x50,0x06,1,0xcd,0x34,0x12,0xc1,0xe1,0xc9));d[0x5000:0x5015]=bytes((0x3e,8,0x47,0xaf,0xe0,0x95,0xe0,0x9a,0xe0,0x9b,0xe0,0x9c,0xe0,0x9d,0xf0,0x99,0xcb,0x3f,0xe0,0x99,0x30));f=M.locate(bytes(d))[0];self.assertEqual(f['far_call']['target'],{'bank':1,'address':0x5000,'rom_offset':0x5000});self.assertEqual(f['far_call']['bankswitch']['address'],0x1234)
 def test_rejects_noncore_target(self):self.assertEqual(M.locate(bytes(0x8000)),[])
if __name__=='__main__':unittest.main()
