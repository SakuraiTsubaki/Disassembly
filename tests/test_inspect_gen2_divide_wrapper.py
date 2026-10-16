import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];S=importlib.util.spec_from_file_location('m',R/'tools/inspect_gen2_divide_wrapper.py');M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_extracts_homecall(self):
  d=bytearray(0x10000);d[0x100:0x112]=bytes((0xe5,0xd5,0xc5,0xf0,0x9f,0xf5,0x3e,1,0xd7,0xcd,0x10,0x6b,0xf1,0xd7,0xc1,0xd1,0xe1,0xc9));f=M.inspect(bytes(d),0x100);self.assertEqual(f['home_call']['target'],{'bank':1,'address':0x6b10,'rom_offset':0x6b10});self.assertEqual(f['home_call']['saved_rom_bank_hram_address'],0xff9f);self.assertEqual(f['preserved_registers'],['AF','BC','DE','HL'])
 def test_rejects_wrong_bankswitch_vector(self):
  d=bytes((0xe5,0xd5,0xc5,0xf0,0x9f,0xf5,0x3e,1,0xcf,0xcd,0x10,0x6b,0xf1,0xd7,0xc1,0xd1,0xe1,0xc9));self.assertIsNone(M.inspect(d,0))
if __name__=='__main__':unittest.main()
