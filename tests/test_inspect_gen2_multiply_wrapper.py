import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_multiply_wrapper.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_extracts_far_target(self):
  d=bytearray(0x10000);d[0x100:0x10b]=bytes((0xe5,0xc5,0x21,0xb0,0x6a,0x3e,1,0xcf,0xc1,0xe1,0xc9));f=M.inspect(bytes(d),0x100);self.assertEqual(f['far_call']['target'],{'bank':1,'address':0x6ab0,'rom_offset':0x6ab0});self.assertEqual(f['preserved_registers'],['BC','HL'])
 def test_rejects_bank_zero(self):self.assertIsNone(M.inspect(bytes((0xe5,0xc5,0x21,0xb0,0x6a,0x3e,0,0xcf,0xc1,0xe1,0xc9)),0))
if __name__=='__main__':unittest.main()
